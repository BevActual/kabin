use serde::Serialize;
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;

use crate::catalog::{LaunchPlan, LibrarySnapshot};

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

    pub fn progress_fields(&self, item_id: &str) -> (f64, f64, u32) {
        let Some(entry) = self.data.get("progress").and_then(|p| p.get(item_id)) else {
            return (0.0, 0.0, 0);
        };
        let position = entry.get("position").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let duration = entry.get("duration").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let track = entry
            .get("track")
            .and_then(|v| v.as_u64())
            .unwrap_or(0) as u32;
        (position, duration, track)
    }

    pub fn save_progress(
        &mut self,
        item_id: &str,
        position: f64,
        duration: f64,
        track: u32,
    ) -> Result<(), String> {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);
        let progress = self
            .data
            .as_object_mut()
            .expect("config root")
            .entry("progress")
            .or_insert_with(|| json!({}));
        if let Some(obj) = progress.as_object_mut() {
            obj.insert(
                item_id.to_string(),
                json!({
                    "position": position.max(0.0),
                    "duration": duration.max(0.0),
                    "track": track,
                    "updated_at": now,
                }),
            );
        }
        self.save()
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

    pub fn rom_dirs_raw(&self) -> Vec<Value> {
        self.data
            .get("rom_dirs")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default()
    }

    pub fn emulation_settings(&self) -> Option<&Value> {
        self.data.get("emulation")
    }

    pub fn sources_map(&self) -> serde_json::Map<String, Value> {
        let default = serde_json::json!({
            "steam": true,
            "desktop": true,
            "roms": true,
            "remote": true,
            "book": true,
            "comic": true,
            "music": true,
            "video": true,
            "tv": true,
        });
        let mut map = default.as_object().cloned().unwrap_or_default();
        if let Some(custom) = self.data.get("sources").and_then(|v| v.as_object()) {
            for (key, value) in custom {
                map.insert(key.clone(), value.clone());
            }
        }
        map
    }

    pub fn set_source_enabled(&mut self, key: &str, enabled: bool) {
        let sources = self
            .data
            .as_object_mut()
            .expect("config root")
            .entry("sources")
            .or_insert_with(|| json!({}));
        if let Some(obj) = sources.as_object_mut() {
            obj.insert(key.to_string(), json!(enabled));
        }
    }

    pub fn add_media_dir(&mut self, path: &str, media_type: &str) {
        let entry = json!({ "path": path, "media_type": media_type });
        let dirs = self
            .data
            .as_object_mut()
            .expect("config root")
            .entry("media_dirs")
            .or_insert_with(|| json!([]));
        if let Some(arr) = dirs.as_array_mut() {
            arr.push(entry);
        }
    }

    pub fn touch_recent(&mut self, title_id: &str) {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);
        let recent = self
            .data
            .as_object_mut()
            .expect("config root")
            .entry("recent")
            .or_insert_with(|| json!({}));
        if let Some(obj) = recent.as_object_mut() {
            obj.insert(title_id.to_string(), json!(now));
        }
    }

    pub fn save(&self) -> Result<(), String> {
        if let Some(parent) = self.path.parent() {
            std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let payload = serde_json::to_string_pretty(&self.data).map_err(|e| e.to_string())?;
        let pid = std::process::id();
        let temporary = self.path.with_file_name(format!(
            ".{}.{}.{}.tmp",
            self.path.file_name().unwrap().to_string_lossy(),
            pid,
            self.path.as_os_str().len()
        ));
        std::fs::write(&temporary, payload).map_err(|e| e.to_string())?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            std::fs::set_permissions(&temporary, std::fs::Permissions::from_mode(0o600))
                .map_err(|e| e.to_string())?;
        }
        std::fs::rename(&temporary, &self.path).map_err(|e| e.to_string())?;
        Ok(())
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
    launch_by_id: HashMap<String, LaunchPlan>,
    items_by_id: HashMap<String, crate::catalog::item::LibraryItem>,
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
                launch_by_id: HashMap::new(),
                items_by_id: HashMap::new(),
            }),
        }
    }
}

impl AppState {
    pub fn invalidate(&self) {
        let mut cache = self.cache.lock().expect("catalog cache poisoned");
        cache.fingerprint.clear();
    }

    pub fn snapshot(&self, force: bool) -> LibrarySnapshot {
        let config = KabinConfig::load();
        let fingerprint = config.library_fingerprint();
        let mut cache = self.cache.lock().expect("catalog cache poisoned");
        if !force && cache.fingerprint == fingerprint {
            return cache.snapshot.clone();
        }
        let (snapshot, launch_by_id, items_by_id) = crate::catalog::build_snapshot(&config);
        cache.fingerprint = fingerprint;
        cache.snapshot = snapshot.clone();
        cache.launch_by_id = launch_by_id;
        cache.items_by_id = items_by_id;
        snapshot
    }

    pub fn launch_plan(&self, title_id: &str) -> Option<LaunchPlan> {
        let cache = self.cache.lock().expect("catalog cache poisoned");
        cache.launch_by_id.get(title_id).cloned()
    }

    pub fn find_item(&self, title_id: &str) -> Option<crate::catalog::item::LibraryItem> {
        let cache = self.cache.lock().expect("catalog cache poisoned");
        cache.items_by_id.get(title_id).cloned()
    }
}
