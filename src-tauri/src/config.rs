use serde::Serialize;
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;

use crate::catalog::LibrarySnapshot;

const FINISHED_RATIO: f32 = 0.9;
const RESUME_AFTER: f32 = 5.0;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AppInfo {
    pub product_name: String,
    pub version: String,
    pub config_path: String,
    pub legacy_python: bool,
    pub window_width: u32,
    pub window_height: u32,
}

#[derive(Debug, Clone)]
pub struct MediaDirConfig {
    pub path: String,
    pub media_type: String,
}

pub fn config_path() -> PathBuf {
    dirs::config_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("kabin")
        .join("config.json")
}

fn legacy_config_path() -> PathBuf {
    dirs::config_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("omagames")
        .join("config.json")
}

#[derive(Debug, Clone)]
pub struct KabinConfig {
    pub path: PathBuf,
    pub data: Value,
}

impl KabinConfig {
    pub fn load() -> Self {
        let path = config_path();
        let load_path = if path.exists() {
            path.clone()
        } else if legacy_config_path().exists() {
            legacy_config_path()
        } else {
            path.clone()
        };
        let data = if load_path.exists() {
            fs::read_to_string(&load_path)
                .ok()
                .and_then(|raw| serde_json::from_str(&raw).ok())
                .unwrap_or_else(|| json!({}))
        } else {
            json!({})
        };
        Self { path, data }
    }

    pub fn hidden_ids(&self) -> HashSet<String> {
        self.data
            .get("hidden")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(str::to_string))
                    .collect()
            })
            .unwrap_or_default()
    }

    pub fn source_enabled(&self, key: &str) -> bool {
        self.data
            .get("sources")
            .and_then(|v| v.get(key))
            .and_then(|v| v.as_bool())
            .unwrap_or(true)
    }

    pub fn steam_root(&self) -> Option<&str> {
        self.data
            .get("steam_root")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
    }

    pub fn media_dirs(&self) -> Vec<MediaDirConfig> {
        self.data
            .get("media_dirs")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|entry| {
                        let path = entry.get("path")?.as_str()?.to_string();
                        let media_type = entry
                            .get("media_type")
                            .and_then(|v| v.as_str())
                            .unwrap_or("book")
                            .to_string();
                        Some(MediaDirConfig { path, media_type })
                    })
                    .collect()
            })
            .unwrap_or_default()
    }

    pub fn recent_ordered(&self) -> Vec<String> {
        let Some(map) = self.data.get("recent").and_then(|v| v.as_object()) else {
            return Vec::new();
        };
        let mut pairs: Vec<(String, f64)> = map
            .iter()
            .filter_map(|(id, ts)| Some((id.clone(), ts.as_f64()?)))
            .collect();
        pairs.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        pairs.into_iter().map(|(id, _)| id).collect()
    }

    pub fn progress_ratio(&self, item_id: &str, track_total: u32) -> Option<f32> {
        let entry = self.data.get("progress")?.get(item_id)?;
        let position = entry.get("position").and_then(|v| v.as_f64()).unwrap_or(0.0) as f32;
        let duration = entry.get("duration").and_then(|v| v.as_f64()).unwrap_or(0.0) as f32;
        let track = entry
            .get("track")
            .and_then(|v| v.as_u64())
            .unwrap_or(0) as u32;
        let total = track_total.max(1);
        if total > 1 {
            let frac = if duration > 0.0 {
                position / duration
            } else {
                0.0
            };
            let ratio = (track as f32 + frac.clamp(0.0, 1.0)) / total as f32;
            if ratio >= FINISHED_RATIO {
                return None;
            }
            return if track > 0 || position >= RESUME_AFTER {
                Some(ratio)
            } else {
                None
            };
        }
        if position < RESUME_AFTER || duration <= 0.0 {
            return None;
        }
        if position >= duration * FINISHED_RATIO {
            return None;
        }
        Some((position / duration).min(1.0))
    }

    pub fn library_fingerprint(&self) -> String {
        let neutral = [
            "recent", "play_counts", "play_time", "progress", "window",
        ];
        let mut relevant = serde_json::Map::new();
        if let Some(obj) = self.data.as_object() {
            for (key, value) in obj {
                if !neutral.contains(&key.as_str()) {
                    relevant.insert(key.clone(), value.clone());
                }
            }
        }
        serde_json::to_string(&relevant).unwrap_or_default()
    }
}

pub fn app_info() -> AppInfo {
    let cfg = KabinConfig::load();
    let window = cfg.data.get("window").and_then(|w| w.as_object());
    let width = window
        .and_then(|w| w.get("width"))
        .and_then(|v| v.as_u64())
        .unwrap_or(1100) as u32;
    let height = window
        .and_then(|w| w.get("height"))
        .and_then(|v| v.as_u64())
        .unwrap_or(720) as u32;

    AppInfo {
        product_name: "Kabin".into(),
        version: env!("CARGO_PKG_VERSION").into(),
        config_path: cfg.path.to_string_lossy().into_owned(),
        legacy_python: true,
        window_width: width,
        window_height: height,
    }
}

pub struct AppState {
    cache: Mutex<CatalogCache>,
}

struct CatalogCache {
    fingerprint: String,
    snapshot: LibrarySnapshot,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            cache: Mutex::new(CatalogCache {
                fingerprint: String::new(),
                snapshot: LibrarySnapshot {
                    shelves: Vec::new(),
                    titles: Vec::new(),
                    counts: HashMap::new(),
                    errors: Vec::new(),
                    fingerprint: String::new(),
                },
            }),
        }
    }
}

impl AppState {
    pub fn snapshot(&self, force: bool) -> LibrarySnapshot {
        let config = KabinConfig::load();
        let fingerprint = config.library_fingerprint();
        let mut cache = self.cache.lock().expect("catalog cache poisoned");
        if !force && cache.fingerprint == fingerprint {
            return cache.snapshot.clone();
        }
        let snapshot = crate::catalog::build_snapshot(&config);
        cache.fingerprint = fingerprint;
        cache.snapshot = snapshot.clone();
        snapshot
    }
}
