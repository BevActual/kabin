use std::collections::HashMap;
use std::path::PathBuf;

use serde_json::{json, Value};

use crate::catalog::item::LibraryItem;
use crate::catalog::launch::LaunchPlan;
use crate::catalog::playback::{path_allowed, playable_tracks};
use crate::config::KabinConfig;

const READABLE_KINDS: &[&str] = &["book", "comic"];

pub fn plays_in_kabin(item: &LibraryItem) -> bool {
    matches!(item.kind_id.as_str(), "music" | "video" | "tv")
}

pub fn opens_in_reader(item: &LibraryItem) -> bool {
    READABLE_KINDS.contains(&item.kind_id.as_str())
}

pub fn tracks_progress(item: &LibraryItem) -> bool {
    plays_in_kabin(item) || opens_in_reader(item)
}

pub fn public_progress(info: &Value) -> Value {
    json!({
        "position": info.get("position").and_then(|v| v.as_f64()).unwrap_or(0.0),
        "duration": info.get("duration").and_then(|v| v.as_f64()).unwrap_or(0.0),
        "track": info.get("track").and_then(|v| v.as_u64()).unwrap_or(0),
        "scroll": info
            .get("scroll")
            .and_then(|v| v.as_f64())
            .map(|s| s.clamp(0.0, 1.0))
            .unwrap_or(0.0),
        "updated_at": info.get("updated_at").and_then(|v| v.as_f64()).unwrap_or(0.0),
    })
}

pub fn progress_for(config: &KabinConfig, item_id: &str) -> Value {
    let Some(entry) = config.data.get("progress").and_then(|p| p.get(item_id)) else {
        return json!({
            "position": 0.0,
            "duration": 0.0,
            "track": 0,
            "scroll": 0.0,
            "updated_at": 0.0,
        });
    };
    public_progress(entry)
}

pub fn media_file_for_item(
    item: &LibraryItem,
    config: &KabinConfig,
    track: usize,
) -> Option<PathBuf> {
    if plays_in_kabin(item) {
        let tracks = playable_tracks(item, config);
        return tracks.into_iter().nth(track);
    }
    if opens_in_reader(item) {
        if let LaunchPlan::OpenPath { path } = &item.launch {
            if path.is_file() && path_allowed(config, path) {
                return Some(path.clone());
            }
        }
    }
    None
}

fn item_size(item: &LibraryItem) -> u64 {
    if let LaunchPlan::OpenPath { path } = &item.launch {
        if path.is_file() {
            return path.metadata().map(|m| m.len()).unwrap_or(0);
        }
    }
    0
}

pub fn serialize_item(item: &LibraryItem, config: &KabinConfig, with_progress: bool) -> Value {
    let media_type = if item.kind_id == "game" {
        "game"
    } else {
        item.kind_id.as_str()
    };
    let appid = match &item.launch {
        LaunchPlan::Steam { appid } => appid.clone(),
        _ => String::new(),
    };
    let has_media = media_file_for_item(item, config, 0).is_some();
    let playable = (plays_in_kabin(item) || opens_in_reader(item)) && has_media;
    let track_count = if plays_in_kabin(item) {
        let n = playable_tracks(item, config).len();
        if n > 0 {
            n as u32
        } else {
            item.track_count.max(1)
        }
    } else {
        0
    };
    let mut public = json!({
        "id": item.id,
        "title": item.title,
        "media_type": media_type,
        "media_format": "",
        "category": "",
        "genres": [],
        "creators": [],
        "series": "",
        "series_index": null,
        "source": item.source,
        "section": item.subtitle,
        "system": if media_type == "game" { item.subtitle.clone() } else { String::new() },
        "appid": appid,
        "has_artwork": item.cover_path.is_some() || !appid.is_empty(),
        "playable": playable,
        "track_count": track_count,
    });
    if with_progress {
        let progress = progress_for(config, &item.id);
        if let Some(obj) = public.as_object_mut() {
            obj.insert("progress".to_string(), public_progress(&progress));
            if READABLE_KINDS.contains(&item.kind_id.as_str()) {
                obj.insert("size".to_string(), json!(item_size(item)));
            }
        }
    }
    public
}

pub fn catalog_counts(items: &[Value]) -> HashMap<String, u32> {
    let mut counts = HashMap::new();
    for item in items {
        let media_type = item
            .get("media_type")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown");
        *counts.entry(media_type.to_string()).or_insert(0) += 1;
    }
    counts
}
