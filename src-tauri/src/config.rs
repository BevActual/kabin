use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use rand::Rng;
use sha2::{Digest, Sha256};
use subtle::ConstantTimeEq;

use crate::catalog::{LaunchPlan, LibrarySnapshot};

const FINISHED_RATIO: f32 = 0.9;
const RESUME_AFTER: f32 = 5.0;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RemoteHostEntry {
    pub name: String,
    pub address: String,
    pub port: u16,
    pub tls: bool,
    pub fingerprint: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub token: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RemoteHostSummary {
    pub name: String,
    pub address: String,
    pub port: u16,
    pub tls: bool,
    pub fingerprint: String,
    pub paired: bool,
}

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

    pub fn adopt_progress(
        &mut self,
        item_id: &str,
        payload: &serde_json::Value,
        save: bool,
    ) -> bool {
        let incoming_updated = payload
            .get("updated_at")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        if incoming_updated <= 0.0 {
            return false;
        }
        let local_updated = self
            .data
            .get("progress")
            .and_then(|p| p.get(item_id))
            .and_then(|e| e.get("updated_at"))
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        if incoming_updated <= local_updated {
            return false;
        }
        let progress = self
            .data
            .as_object_mut()
            .expect("config root")
            .entry("progress")
            .or_insert_with(|| json!({}));
        if let Some(obj) = progress.as_object_mut() {
            obj.insert(item_id.to_string(), payload.clone());
        }
        if save {
            let _ = self.save();
        }
        true
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

    pub fn add_rom_dir(
        &mut self,
        path: &str,
        system: &str,
        emulator: serde_json::Value,
        extensions: Vec<String>,
    ) {
        let mut entry = serde_json::Map::from_iter([
            ("path".into(), json!(path)),
            ("system".into(), json!(system)),
            ("emulator".into(), emulator),
            ("extensions".into(), json!(extensions)),
        ]);
        if let Some(bios) = self
            .emulation_settings()
            .and_then(|e| e.get("bios"))
            .and_then(|b| b.get(system))
            .and_then(|v| v.as_str())
        {
            entry.insert("bios_path".into(), json!(bios));
        }
        let entry = Value::Object(entry);
        let dirs = self
            .data
            .as_object_mut()
            .expect("config root")
            .entry("rom_dirs")
            .or_insert_with(|| json!([]));
        if let Some(arr) = dirs.as_array_mut() {
            arr.push(entry);
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

    fn network_mut(&mut self) -> &mut serde_json::Map<String, Value> {
        let root = self.data.as_object_mut().expect("config root");
        if !root.contains_key("network") {
            root.insert("network".into(), default_network());
        }
        root.get_mut("network")
            .and_then(|v| v.as_object_mut())
            .expect("network object")
    }

    fn network(&self) -> Value {
        self.data
            .get("network")
            .cloned()
            .unwrap_or_else(default_network)
    }

    pub fn host_enabled(&self) -> bool {
        self.network()
            .get("host_enabled")
            .and_then(|v| v.as_bool())
            .unwrap_or(false)
    }

    pub fn host_port(&self) -> u16 {
        self.network()
            .get("port")
            .and_then(|v| v.as_u64())
            .unwrap_or(42424) as u16
    }

    pub fn host_name(&self) -> String {
        self.network()
            .get("host_name")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .map(str::to_string)
            .unwrap_or_else(default_host_name)
    }

    pub fn set_host_enabled(&mut self, enabled: bool) {
        self.network_mut()
            .insert("host_enabled".into(), json!(enabled));
    }

    pub fn ensure_network_token(&mut self) -> Result<String, String> {
        let missing = self
            .network()
            .get("token")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .is_none();
        if missing {
            self.network_mut()
                .insert("token".into(), json!(new_network_token()));
            self.save()?;
        }
        Ok(self
            .network()
            .get("token")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string())
    }

    pub fn network_token_valid(&self, token: &str) -> bool {
        if token.is_empty() {
            return false;
        }
        if let Some(master) = self
            .network()
            .get("token")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            if master.as_bytes().ct_eq(token.as_bytes()).into() {
                return true;
            }
        }
        let digest = hex::encode(Sha256::digest(token.as_bytes()));
        self.network()
            .get("paired_devices")
            .and_then(|v| v.as_array())
            .map(|devices| {
                devices.iter().any(|device| {
                    device
                        .get("token_hash")
                        .and_then(|v| v.as_str())
                        .map(|hash| hash.as_bytes().ct_eq(digest.as_bytes()).into())
                        .unwrap_or(false)
                })
            })
            .unwrap_or(false)
    }

    pub fn remote_hosts(&self) -> Vec<RemoteHostEntry> {
        self.network()
            .get("remote_hosts")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|entry| {
                        Some(RemoteHostEntry {
                            name: entry.get("name")?.as_str()?.to_string(),
                            address: entry.get("address")?.as_str()?.to_string(),
                            port: entry.get("port")?.as_u64()? as u16,
                            tls: entry.get("tls").and_then(|v| v.as_bool()).unwrap_or(true),
                            fingerprint: entry
                                .get("fingerprint")
                                .and_then(|v| v.as_str())
                                .unwrap_or("")
                                .to_string(),
                            token: entry
                                .get("token")
                                .and_then(|v| v.as_str())
                                .map(str::to_string),
                        })
                    })
                    .collect()
            })
            .unwrap_or_default()
    }

    pub fn remote_host_summaries(&self) -> Vec<RemoteHostSummary> {
        self.remote_hosts()
            .into_iter()
            .map(|host| RemoteHostSummary {
                name: host.name,
                address: host.address,
                port: host.port,
                tls: host.tls,
                fingerprint: host.fingerprint,
                paired: true,
            })
            .collect()
    }

    pub fn remote_host_by_name(&self, name: &str) -> Option<RemoteHostEntry> {
        self.remote_hosts()
            .into_iter()
            .find(|host| host.name == name)
    }

    pub fn save_remote_host(&mut self, host: RemoteHostEntry, token: String) -> Result<(), String> {
        let network = self.network_mut();
        let hosts = network
            .entry("remote_hosts".to_string())
            .or_insert_with(|| json!([]));
        let Some(arr) = hosts.as_array_mut() else {
            return Err("remote_hosts must be an array".into());
        };
        arr.retain(|entry| entry.get("name").and_then(|v| v.as_str()) != Some(host.name.as_str()));
        arr.push(json!({
            "name": host.name,
            "address": host.address,
            "port": host.port,
            "token": token,
            "tls": host.tls,
            "fingerprint": host.fingerprint,
        }));
        self.save()
    }

    pub fn remove_remote_host(&mut self, name: &str) -> Result<(), String> {
        let network = self.network_mut();
        let hosts = network
            .entry("remote_hosts".to_string())
            .or_insert_with(|| json!([]));
        if let Some(arr) = hosts.as_array_mut() {
            arr.retain(|entry| entry.get("name").and_then(|v| v.as_str()) != Some(name));
        }
        self.save()
    }

    pub fn add_paired_device(&mut self, name: &str) -> String {
        let token = new_network_token();
        let digest = hex::encode(Sha256::digest(token.as_bytes()));
        let network = self.network_mut();
        let devices = network
            .entry("paired_devices".to_string())
            .or_insert_with(|| json!([]));
        if let Some(arr) = devices.as_array_mut() {
            arr.push(json!({
                "name": name,
                "token_hash": digest,
            }));
        }
        let _ = self.save();
        token
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

#[derive(Clone)]
pub struct AppState {
    cache: Arc<Mutex<CatalogCache>>,
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
            cache: Arc::new(Mutex::new(CatalogCache {
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
            })),
        }
    }
}

fn default_network() -> Value {
    json!({
        "host_enabled": false,
        "host_name": "",
        "port": 42424,
        "token": "",
        "paired_devices": [],
        "remote_hosts": [],
    })
}

fn default_host_name() -> String {
    std::env::var("HOSTNAME")
        .ok()
        .filter(|s| !s.is_empty())
        .or_else(|| {
            fs::read_to_string("/etc/hostname")
                .ok()
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
        })
        .unwrap_or_else(|| "Kabin".into())
}

fn new_network_token() -> String {
    let bytes: [u8; 32] = rand::thread_rng().gen();
    URL_SAFE_NO_PAD.encode(bytes)
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
