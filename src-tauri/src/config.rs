use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;

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

pub fn config_path() -> PathBuf {
    dirs::config_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("kabin")
        .join("config.json")
}

fn read_config_value() -> Value {
    let path = config_path();
    if !path.exists() {
        return Value::Object(Default::default());
    }
    fs::read_to_string(&path)
        .ok()
        .and_then(|raw| serde_json::from_str(&raw).ok())
        .unwrap_or(Value::Object(Default::default()))
}

pub fn app_info() -> AppInfo {
    let cfg = read_config_value();
    let window = cfg.get("window").and_then(|w| w.as_object());
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
        config_path: config_path().to_string_lossy().into_owned(),
        legacy_python: true,
        window_width: width,
        window_height: height,
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CatalogTitle {
    pub id: String,
    pub title: String,
    pub subtitle: String,
    pub kind: String,
    pub aspect: String,
    pub progress: Option<f32>,
    pub accent_hue: u16,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HomeShelf {
    pub id: String,
    pub label: String,
    pub titles: Vec<CatalogTitle>,
}

/// Placeholder catalog until Rust library scanners replace the Python sources.
pub fn sample_home_shelves() -> Vec<HomeShelf> {
    vec![
        HomeShelf {
            id: "continue".into(),
            label: "Continue".into(),
            titles: vec![
                CatalogTitle {
                    id: "demo-1".into(),
                    title: "Stellar Drift".into(),
                    subtitle: "Resume · 42%".into(),
                    kind: "game".into(),
                    aspect: "poster".into(),
                    progress: Some(0.42),
                    accent_hue: 210,
                },
                CatalogTitle {
                    id: "demo-2".into(),
                    title: "Midnight Transit".into(),
                    subtitle: "Chapter 8".into(),
                    kind: "book".into(),
                    aspect: "poster".into(),
                    progress: Some(0.61),
                    accent_hue: 32,
                },
            ],
        },
        HomeShelf {
            id: "recent".into(),
            label: "Recently Added".into(),
            titles: vec![
                CatalogTitle {
                    id: "demo-3".into(),
                    title: "Neon Circuit".into(),
                    subtitle: "Album".into(),
                    kind: "music".into(),
                    aspect: "square".into(),
                    progress: None,
                    accent_hue: 280,
                },
                CatalogTitle {
                    id: "demo-4".into(),
                    title: "Harbor Lights".into(),
                    subtitle: "1h 48m".into(),
                    kind: "video".into(),
                    aspect: "widescreen".into(),
                    progress: None,
                    accent_hue: 195,
                },
                CatalogTitle {
                    id: "demo-5".into(),
                    title: "Vector Prime".into(),
                    subtitle: "SNES".into(),
                    kind: "game".into(),
                    aspect: "poster".into(),
                    progress: None,
                    accent_hue: 145,
                },
            ],
        },
    ]
}

pub fn sample_library(kind: &str) -> Vec<CatalogTitle> {
    sample_home_shelves()
        .into_iter()
        .flat_map(|s| s.titles)
        .filter(|t| t.kind == kind)
        .collect()
}

pub struct AppState {
    pub _lock: Mutex<()>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            _lock: Mutex::new(()),
        }
    }
}
