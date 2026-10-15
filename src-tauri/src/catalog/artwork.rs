use std::path::{Path, PathBuf};

use super::item::LibraryItem;
use super::launch::LaunchPlan;

const IMAGE_SUFFIXES: [&str; 4] = [".jpg", ".jpeg", ".png", ".webp"];

pub fn is_safe_artwork_file(path: &Path) -> bool {
    let Ok(resolved) = path.canonicalize() else {
        return false;
    };
    if resolved.is_symlink() || !resolved.is_file() {
        return false;
    }
    true
}

pub fn steam_cached_cover(appid: &str) -> Option<PathBuf> {
    let base = dirs::cache_dir().unwrap_or_else(|| PathBuf::from(".cache"));
    let primary = base
        .join("kabin")
        .join("steam")
        .join("cover")
        .join(format!("{appid}.jpg"));
    if primary.is_file() {
        return Some(primary);
    }
    let legacy = base
        .join("omagames")
        .join("steam")
        .join("cover")
        .join(format!("{appid}.jpg"));
    if legacy.is_file() {
        return Some(legacy);
    }
    None
}

pub fn artwork_file_for_item(item: &LibraryItem) -> Option<PathBuf> {
    if let Some(cover) = item
        .cover_path
        .as_ref()
        .map(PathBuf::from)
        .filter(|p| is_safe_artwork_file(p))
    {
        return Some(cover);
    }
    match &item.launch {
        LaunchPlan::Steam { appid } => steam_cached_cover(appid),
        LaunchPlan::RemoteGame { appid, .. } if !appid.is_empty() => steam_cached_cover(appid),
        _ => None,
    }
}

pub fn local_cover(path: &Path) -> Option<PathBuf> {
    let parent = path.parent()?;
    for suffix in IMAGE_SUFFIXES {
        let sidecar = path.with_extension(suffix.trim_start_matches('.'));
        if sidecar.is_file() {
            return Some(sidecar);
        }
    }
    let stem = path.file_stem()?.to_string_lossy();
    for subdir in ["covers", "media"] {
        let folder = parent.join(subdir);
        if !folder.is_dir() {
            continue;
        }
        for suffix in IMAGE_SUFFIXES {
            let candidate = folder.join(format!("{stem}{suffix}"));
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    None
}

pub fn folder_cover(directory: &Path) -> Option<PathBuf> {
    if !directory.is_dir() {
        return None;
    }
    for name in ["cover", "folder", "front", "album", "poster"] {
        for suffix in IMAGE_SUFFIXES {
            let candidate = directory.join(format!("{name}{suffix}"));
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    None
}
