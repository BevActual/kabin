use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};

use super::artwork::{folder_cover, local_cover};
use super::item::LibraryItem;
use super::kinds::{self, MediaKind};
use super::titles::tidy_filename;

const SKIP_DIRS: [&str; 6] = ["covers", "media", "images", "manuals", "videos", ".git"];

pub struct MediaDirEntry {
    pub path: PathBuf,
    pub media_type: String,
}

fn item_id(kind_id: &str, base: &Path, target: &Path) -> String {
    match target.strip_prefix(base) {
        Ok(relative) if relative.parent().is_none_or(|p| p.as_os_str().is_empty()) => {
            format!("{kind_id}:{}", target.file_name().unwrap().to_string_lossy())
        }
        Ok(relative) => format!("{kind_id}:{}", relative.to_string_lossy().replace('\\', "/")),
        Err(_) => format!("{kind_id}:{}", target.file_name().unwrap().to_string_lossy()),
    }
}

fn safe_mtime(path: &Path) -> f64 {
    path.metadata()
        .ok()
        .and_then(|m| m.modified().ok())
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

fn walk_files(base: &Path, visit: &mut dyn FnMut(&Path)) {
    let mut stack = vec![base.to_path_buf()];
    while let Some(dir) = stack.pop() {
        let read = match fs::read_dir(&dir) {
            Ok(r) => r,
            Err(_) => continue,
        };
        let mut entries: Vec<_> = read.filter_map(Result::ok).collect();
        entries.sort_by_key(|e| e.file_name());
        for entry in entries {
            let path = entry.path();
            if path.is_dir() {
                let name = entry.file_name();
                let name = name.to_string_lossy();
                if name.starts_with('.') {
                    continue;
                }
                if SKIP_DIRS
                    .iter()
                    .any(|skip| skip.eq_ignore_ascii_case(name.as_ref()))
                {
                    continue;
                }
                stack.push(path);
            } else if path.is_file() {
                visit(&path);
            }
        }
    }
}

fn file_item(
    kind: &MediaKind,
    base: &Path,
    path: &Path,
    hidden: &HashSet<String>,
) -> Option<LibraryItem> {
    let id = item_id(kind.id, base, path);
    if hidden.contains(&id) {
        return None;
    }
    let cover = local_cover(path).or_else(|| folder_cover(path.parent()?));
    Some(LibraryItem {
        id,
        title: tidy_filename(path.file_name()?.to_string_lossy().as_ref()),
        subtitle: kind.label.to_string(),
        kind_id: kind.id.to_string(),
        source: kind.id.to_string(),
        cover_path: cover.map(|p| p.to_string_lossy().into_owned()),
        added_at: safe_mtime(path),
        track_count: 1,
    })
}

fn album_item(
    kind: &MediaKind,
    base: &Path,
    folder: &Path,
    tracks: &[PathBuf],
    hidden: &HashSet<String>,
) -> Option<LibraryItem> {
    let id = item_id(kind.id, base, folder);
    if hidden.contains(&id) {
        return None;
    }
    let cover = folder_cover(folder).or_else(|| local_cover(&tracks[0]));
    Some(LibraryItem {
        id,
        title: tidy_filename(folder.file_name()?.to_string_lossy().as_ref()),
        subtitle: kind.plural.to_string(),
        kind_id: kind.id.to_string(),
        source: kind.id.to_string(),
        cover_path: cover.map(|p| p.to_string_lossy().into_owned()),
        added_at: safe_mtime(folder),
        track_count: tracks.len() as u32,
    })
}

fn scan_kind(kind: &MediaKind, base: &Path, hidden: &HashSet<String>) -> Vec<LibraryItem> {
    if kind.id == "music" {
        let mut albums: HashMap<PathBuf, Vec<PathBuf>> = HashMap::new();
        let mut loose: Vec<PathBuf> = Vec::new();
        walk_files(base, &mut |path| {
            let ext = path
                .extension()
                .and_then(|e| e.to_str())
                .map(|e| format!(".{e}"))
                .unwrap_or_default()
                .to_lowercase();
            if !kinds::extension_matches(kind, &ext) {
                return;
            }
            if path.parent() == Some(base) {
                loose.push(path.to_path_buf());
            } else if let Some(parent) = path.parent() {
                albums.entry(parent.to_path_buf()).or_default().push(path.to_path_buf());
            }
        });
        let mut items = Vec::new();
        let mut album_pairs: Vec<_> = albums.into_iter().collect();
        album_pairs.sort_by_key(|(folder, _)| folder.clone());
        for (folder, tracks) in album_pairs {
            if let Some(item) = album_item(kind, base, &folder, &tracks, hidden) {
                items.push(item);
            }
        }
        loose.sort();
        for path in loose {
            if let Some(item) = file_item(kind, base, &path, hidden) {
                items.push(item);
            }
        }
        return items;
    }

    let mut items = Vec::new();
    walk_files(base, &mut |path| {
        let ext = path
            .extension()
            .and_then(|e| e.to_str())
            .map(|e| format!(".{e}"))
            .unwrap_or_default()
            .to_lowercase();
        if !kinds::extension_matches(kind, &ext) {
            return;
        }
        if let Some(item) = file_item(kind, base, path, hidden) {
            items.push(item);
        }
    });
    items
}

pub fn scan_media_dirs(
    entries: &[MediaDirEntry],
    hidden: &HashSet<String>,
    enabled_kinds: &HashSet<String>,
) -> Vec<LibraryItem> {
    let mut items = Vec::new();
    for entry in entries {
        let kind = kinds::kind_by_id(&entry.media_type);
        if !enabled_kinds.contains(kind.id) {
            continue;
        }
        if !entry.path.is_dir() {
            continue;
        }
        items.extend(scan_kind(kind, &entry.path, hidden));
    }
    items
}
