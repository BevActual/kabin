use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};

use serde::Serialize;

use super::item::LibraryItem;
use super::playback::{path_allowed, playable_tracks};
use super::reader_comic;
use crate::config::KabinConfig;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ReaderSession {
    pub title_id: String,
    pub title: String,
    pub backend: String,
    pub file_path: Option<String>,
    pub pages: Vec<String>,
    pub initial_page: u32,
    pub page_count: u32,
}

fn backend_for_suffix(suffix: &str) -> Option<&'static str> {
    match suffix.to_lowercase().as_str() {
        ".pdf" => Some("pdf"),
        ".epub" => Some("epub"),
        ".cbz" => Some("cbz"),
        ".txt" => Some("txt"),
        ".fb2" => Some("fb2"),
        ".mobi" | ".azw3" => Some("external"),
        ".cbr" if reader_comic::bsdtar_available() => Some("comic-archive"),
        ".cbt" if reader_comic::bsdtar_available() => Some("comic-archive"),
        ".cb7" if reader_comic::bsdtar_available() => Some("comic-archive"),
        _ => None,
    }
}

pub(crate) fn reader_cache_root(title_id: &str) -> PathBuf {
    let base = dirs::cache_dir().unwrap_or_else(|| PathBuf::from(".cache"));
    let safe: String = title_id
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() { c } else { '_' })
        .collect();
    base.join("kabin").join("reader").join(safe)
}

fn extract_cbz(archive: &Path, title_id: &str) -> Result<Vec<PathBuf>, String> {
    let out = reader_cache_root(title_id);
    let manifest = out.join(".manifest");
    if manifest.is_file() {
        let list = fs::read_to_string(&manifest).map_err(|e| e.to_string())?;
        let paths: Vec<PathBuf> = list
            .lines()
            .filter(|l| !l.is_empty())
            .map(PathBuf::from)
            .filter(|p| p.is_file())
            .collect();
        if !paths.is_empty() {
            return Ok(paths);
        }
    }
    fs::create_dir_all(&out).map_err(|e| e.to_string())?;
    let file = fs::File::open(archive).map_err(|e| e.to_string())?;
    let mut zip = zip::ZipArchive::new(file).map_err(|e| e.to_string())?;
    let mut entries: Vec<(String, u16)> = Vec::new();
    for index in 0..zip.len() {
        let entry = zip.by_index(index).map_err(|e| e.to_string())?;
        let name = entry.name().to_string();
        let lower = name.to_lowercase();
        if lower.ends_with(".png")
            || lower.ends_with(".jpg")
            || lower.ends_with(".jpeg")
            || lower.ends_with(".webp")
            || lower.ends_with(".gif")
        {
            entries.push((name, index as u16));
        }
    }
    entries.sort_by(|a, b| a.0.cmp(&b.0));
    let mut paths = Vec::new();
    for (index, (_, zip_index)) in entries.iter().enumerate() {
        let mut entry = zip
            .by_index(*zip_index as usize)
            .map_err(|e| e.to_string())?;
        let dest = out.join(format!("page-{index:04}.img"));
        let mut buffer = Vec::new();
        entry.read_to_end(&mut buffer).map_err(|e| e.to_string())?;
        fs::write(&dest, buffer).map_err(|e| e.to_string())?;
        paths.push(dest);
    }
    fs::write(
        &manifest,
        paths
            .iter()
            .map(|p| p.to_string_lossy())
            .collect::<Vec<_>>()
            .join("\n"),
    )
    .map_err(|e| e.to_string())?;
    Ok(paths)
}

pub fn build_reader_session(item: &LibraryItem, config: &KabinConfig) -> Option<ReaderSession> {
    if !matches!(item.kind_id.as_str(), "book" | "comic" | "pdf") {
        return None;
    }
    let file = if matches!(
        item.launch,
        super::launch::LaunchPlan::RemoteStream { .. }
    ) {
        crate::remote::ensure_remote_media_file(item, config, 0).ok()?
    } else {
        let paths = playable_tracks(item, config);
        paths.first()?.clone()
    };
    if !matches!(
        item.launch,
        super::launch::LaunchPlan::RemoteStream { .. }
    ) && !path_allowed(config, &file)
    {
        return None;
    }
    let suffix: String = file
        .extension()
        .map(|e| format!(".{}", e.to_string_lossy()))
        .unwrap_or_default();
    let backend = backend_for_suffix(&suffix)?;
    let (initial_page, page_count, file_path, pages) = match backend {
        "cbz" => {
            let paths = extract_cbz(&file, &item.id).ok()?;
            comic_session_pages(config, &item.id, paths)
        }
        "comic-archive" => {
            let paths = reader_comic::extract_bsdtar_comic(&file, &item.id).ok()?;
            comic_session_pages(config, &item.id, paths)
        }
        "fb2" => {
            let html_pages = super::fb2::extract_fb2_pages(&file, &item.id).ok()?;
            let count = html_pages.len() as u32;
            let (pos, dur, _) = config.progress_fields(&item.id);
            let page = resume_page(pos, dur, count);
            (
                page,
                count.max(1),
                None,
                html_pages,
            )
        }
        "external" => {
            let path = file.to_string_lossy().into_owned();
            return Some(ReaderSession {
                title_id: item.id.clone(),
                title: item.title.clone(),
                backend: "external".into(),
                file_path: Some(path),
                pages: Vec::new(),
                initial_page: 0,
                page_count: 1,
            });
        }
        _ => {
            let (pos, dur, _) = config.progress_fields(&item.id);
            (
                resume_page(pos, dur, 1),
                1,
                Some(file.to_string_lossy().into_owned()),
                Vec::new(),
            )
        }
    };
    Some(ReaderSession {
        title_id: item.id.clone(),
        title: item.title.clone(),
        backend: backend.to_string(),
        file_path,
        pages,
        initial_page,
        page_count,
    })
}

fn comic_session_pages(
    config: &KabinConfig,
    item_id: &str,
    paths: Vec<PathBuf>,
) -> (u32, u32, Option<String>, Vec<String>) {
    let count = paths.len() as u32;
    let (pos, dur, _) = config.progress_fields(item_id);
    let page = if dur > 0.0 {
        resume_page(pos, dur, count)
    } else {
        0
    };
    (
        page,
        count.max(1),
        None,
        paths
            .into_iter()
            .map(|p| p.to_string_lossy().into_owned())
            .collect(),
    )
}

fn resume_page(position: f64, duration: f64, max: u32) -> u32 {
    if position <= 0.0 {
        return 0;
    }
    if duration > 0.0 && position >= duration * 0.9 {
        return 0;
    }
    (position as u32).min(max.saturating_sub(1))
}
