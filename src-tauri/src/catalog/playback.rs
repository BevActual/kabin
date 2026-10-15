use std::path::{Path, PathBuf};

use serde::Serialize;

use super::item::LibraryItem;
use super::kinds::{extension_matches, kind_by_id};
use crate::config::KabinConfig;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PlaybackTrack {
    pub path: String,
    pub label: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PlaybackSession {
    pub title_id: String,
    pub title: String,
    pub subtitle: String,
    pub kind: String,
    pub tracks: Vec<PlaybackTrack>,
    pub initial_track: u32,
    pub initial_position: f64,
}

fn expand_path(raw: &str) -> PathBuf {
    if raw.starts_with('~') {
        if let Some(home) = dirs::home_dir() {
            return home.join(raw.trim_start_matches('~').trim_start_matches('/'));
        }
    }
    PathBuf::from(raw)
}

pub fn path_allowed(config: &KabinConfig, path: &Path) -> bool {
    let Ok(resolved) = path.canonicalize() else {
        return false;
    };
    if resolved.is_symlink() {
        return false;
    }
    for entry in config.media_dirs() {
        let root = expand_path(&entry.path);
        let Ok(root) = root.canonicalize() else {
            continue;
        };
        if resolved.starts_with(&root) {
            return true;
        }
    }
    false
}

fn track_sort_key(path: &Path) -> String {
    path.file_name()
        .map(|n| n.to_string_lossy().to_lowercase())
        .unwrap_or_default()
}

fn clean_track_label(filename: &str, album: &str) -> String {
    let mut name = Path::new(filename)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or(filename)
        .replace('_', " ");
    if !album.is_empty() && name.to_lowercase().starts_with(&album.to_lowercase()) {
        if let Some(rest) = name.split(" - ").nth(1) {
            name = rest.to_string();
        }
    }
    name.split_whitespace().collect::<Vec<_>>().join(" ")
}

pub fn playable_tracks(item: &LibraryItem, config: &KabinConfig) -> Vec<PathBuf> {
    let kind = kind_by_id(&item.kind_id);
    if !matches!(kind.id, "music" | "video" | "tv") {
        return Vec::new();
    }
    let path = match &item.launch {
        super::launch::LaunchPlan::OpenPath { path } => path.clone(),
        _ => return Vec::new(),
    };
    if path.is_file() {
        if path_allowed(config, &path) {
            return vec![path];
        }
        return Vec::new();
    }
    if !path.is_dir() {
        return Vec::new();
    }
    let mut tracks = Vec::new();
    let Ok(read) = std::fs::read_dir(&path) else {
        return tracks;
    };
    for entry in read.flatten() {
        let child = entry.path();
        if child.file_name().is_some_and(|n| n.to_string_lossy().starts_with('.')) {
            continue;
        }
        if !child.is_file() {
            continue;
        }
        let ext = child
            .extension()
            .and_then(|e| e.to_str())
            .map(|e| format!(".{e}"))
            .unwrap_or_default()
            .to_lowercase();
        if !extension_matches(kind, &ext) {
            continue;
        }
        if path_allowed(config, &child) {
            tracks.push(child);
        }
    }
    tracks.sort_by_key(|p| track_sort_key(p));
    tracks
}

pub fn build_playback_session(
    item: &LibraryItem,
    config: &KabinConfig,
) -> Option<PlaybackSession> {
    let tracks_paths = playable_tracks(item, config);
    if tracks_paths.is_empty() {
        return None;
    }
    let progress = config.progress_fields(&item.id);
    let initial_track = progress.2.min(tracks_paths.len().saturating_sub(1) as u32);
    let tracks: Vec<PlaybackTrack> = tracks_paths
        .iter()
        .map(|path| PlaybackTrack {
            path: path.to_string_lossy().into_owned(),
            label: clean_track_label(
                path.file_name().unwrap_or_default().to_string_lossy().as_ref(),
                &item.title,
            ),
        })
        .collect();
    Some(PlaybackSession {
        title_id: item.id.clone(),
        title: item.title.clone(),
        subtitle: item.subtitle.clone(),
        kind: item.kind_id.clone(),
        tracks,
        initial_track,
        initial_position: progress.0,
    })
}
