use std::fs;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};

use crate::config::KabinConfig;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Indexer {
    pub id: String,
    pub name: String,
    pub url: String,
    #[serde(default)]
    pub api_key: String,
    pub kind: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UsenetServer {
    #[serde(default)]
    pub host: String,
    #[serde(default)]
    pub port: u16,
    #[serde(default = "default_true")]
    pub ssl: bool,
    #[serde(default)]
    pub username: String,
    #[serde(default)]
    pub password: String,
}

impl Default for UsenetServer {
    fn default() -> Self {
        Self {
            host: String::new(),
            port: 563,
            ssl: true,
            username: String::new(),
            password: String::new(),
        }
    }
}

impl UsenetServer {
    pub fn resolved_port(&self) -> u16 {
        if self.port == 0 {
            if self.ssl { 563 } else { 119 }
        } else {
            self.port
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WantedItem {
    pub id: String,
    pub title: String,
    #[serde(default)]
    pub year: String,
    pub kind: String,
    #[serde(default = "default_quality")]
    pub quality: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DownloadSettings {
    #[serde(default = "default_quality")]
    pub quality: String,
    #[serde(default)]
    pub import_dir: String,
    #[serde(default)]
    pub download_dir: String,
    #[serde(default = "default_connections")]
    pub connections: u16,
    #[serde(default)]
    pub usenet: UsenetServer,
    #[serde(default)]
    pub indexers: Vec<Indexer>,
    #[serde(default)]
    pub wanted: Vec<WantedItem>,
}

impl Default for DownloadSettings {
    fn default() -> Self {
        Self {
            quality: default_quality(),
            import_dir: String::new(),
            download_dir: String::new(),
            connections: default_connections(),
            usenet: UsenetServer::default(),
            indexers: Vec::new(),
            wanted: Vec::new(),
        }
    }
}

fn default_quality() -> String {
    "1080p".into()
}

fn default_connections() -> u16 {
    4
}

fn default_true() -> bool {
    true
}

pub fn load() -> DownloadSettings {
    let config = KabinConfig::load();
    config
        .data
        .get("downloads")
        .and_then(|value| serde_json::from_value(value.clone()).ok())
        .unwrap_or_default()
}

pub fn save(settings: &DownloadSettings) -> Result<(), String> {
    let mut config = KabinConfig::load();
    config.data["downloads"] =
        serde_json::to_value(settings).map_err(|error| error.to_string())?;
    config.save()
}

pub fn new_id() -> String {
    use rand::RngCore;
    let mut bytes = [0u8; 8];
    rand::thread_rng().fill_bytes(&mut bytes);
    hex::encode(bytes)
}

pub fn kabin_download_root() -> PathBuf {
    let settings = load();
    if !settings.download_dir.trim().is_empty() {
        return PathBuf::from(settings.download_dir.trim());
    }
    dirs::download_dir()
        .or_else(dirs::home_dir)
        .unwrap_or_else(|| PathBuf::from("."))
        .join("Kabin")
}

pub fn jobs_path() -> PathBuf {
    dirs::config_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("kabin")
        .join("downloads")
        .join("jobs.json")
}

pub fn ensure_dir(path: &std::path::Path) -> Result<(), String> {
    fs::create_dir_all(path).map_err(|error| error.to_string())
}

pub fn sanitize_name(name: &str) -> String {
    let mut out = String::new();
    for ch in name.chars() {
        if ch.is_ascii_alphanumeric() || matches!(ch, ' ' | '-' | '_' | '.') {
            out.push(ch);
        }
    }
    let trimmed = out.trim().trim_matches('.').to_string();
    if trimmed.is_empty() {
        "download".into()
    } else {
        trimmed.chars().take(80).collect()
    }
}
