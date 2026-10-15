use std::collections::{HashMap, HashSet};

use serde::Serialize;

use super::desktop::scan_desktop;
use super::home::{self, HomeShelf};
use super::item::{CatalogTitle, LibraryItem};
use super::media_dirs::{scan_media_dirs, MediaDirEntry};
use super::roms::scan_rom_dirs;
use super::steam::scan_steam;
use crate::config::KabinConfig;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ScanError {
    pub source: String,
    pub message: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LibrarySnapshot {
    pub shelves: Vec<HomeShelfDto>,
    pub titles: Vec<CatalogTitle>,
    pub counts: HashMap<String, u32>,
    pub errors: Vec<ScanError>,
    pub fingerprint: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HomeShelfDto {
    pub id: String,
    pub label: String,
    pub titles: Vec<CatalogTitle>,
}

impl From<HomeShelf> for HomeShelfDto {
    fn from(value: HomeShelf) -> Self {
        Self {
            id: value.id,
            label: value.label,
            titles: value.titles,
        }
    }
}

pub fn discover_local(config: &KabinConfig) -> (Vec<LibraryItem>, Vec<ScanError>) {
    let hidden = config.hidden_ids();
    let mut items = Vec::new();
    let errors = Vec::new();
    let mut steam_appids = HashSet::new();

    if config.source_enabled("steam") {
        let games = scan_steam(config.steam_root(), &hidden);
        for game in &games {
            if let Some(appid) = game.id.strip_prefix("steam:") {
                steam_appids.insert(appid.to_string());
            }
        }
        items.extend(games);
    }

    if config.source_enabled("desktop") {
        items.extend(scan_desktop(&hidden, &steam_appids));
    }

    if config.source_enabled("roms") {
        items.extend(scan_rom_dirs(
            &config.rom_dirs_raw(),
            &hidden,
            config.emulation_settings(),
        ));
    }

    let folder_kinds: HashSet<String> = ["book", "comic", "music", "video", "tv"]
        .into_iter()
        .filter(|kind| config.source_enabled(kind))
        .map(str::to_string)
        .collect();

    if !folder_kinds.is_empty() {
        let entries: Vec<MediaDirEntry> = config
            .media_dirs()
            .into_iter()
            .filter_map(|entry| {
                let path = expand_path(&entry.path);
                Some(MediaDirEntry {
                    path,
                    media_type: entry.media_type,
                })
            })
            .collect();
        items.extend(scan_media_dirs(&entries, &hidden, &folder_kinds));
    }

    items.sort_by(|a, b| a.sort_key().cmp(&b.sort_key()));
    (items, errors)
}

fn expand_path(raw: &str) -> std::path::PathBuf {
    if raw.starts_with('~') {
        if let Some(home) = dirs::home_dir() {
            return home.join(raw.trim_start_matches('~').trim_start_matches('/'));
        }
    }
    std::path::PathBuf::from(raw)
}

fn count_by_kind(items: &[LibraryItem]) -> HashMap<String, u32> {
    let mut counts = HashMap::new();
    for item in items {
        *counts.entry(item.kind_id.clone()).or_insert(0) += 1;
    }
    counts
}

pub fn build_snapshot(
    config: &KabinConfig,
) -> (
    LibrarySnapshot,
    std::collections::HashMap<String, super::LaunchPlan>,
    std::collections::HashMap<String, super::item::LibraryItem>,
) {
    let fingerprint = config.library_fingerprint();
    let (mut items, mut errors) = discover_local(config);
    super::steam_art::enrich_steam_covers(&mut items);
    if config.source_enabled("remote") {
        let (remote_items, statuses) = crate::remote::discover_remote(config);
        for (name, status) in statuses {
            if status.state != "online" {
                errors.push(ScanError {
                    source: format!("remote:{name}"),
                    message: status.message,
                });
            }
        }
        items.extend(remote_items);
        items.sort_by(|a, b| a.sort_key().cmp(&b.sort_key()));
        let mut cfg = KabinConfig::load();
        if crate::remote::sync_progress_from_remote(&items, &mut cfg) {
            let _ = cfg.save();
        }
    }
    let launch_by_id = items
        .iter()
        .map(|item| (item.id.clone(), item.launch.clone()))
        .collect();
    let items_by_id = items
        .iter()
        .map(|item| (item.id.clone(), item.clone()))
        .collect();
    let shelves: Vec<HomeShelfDto> = home::build_home_shelves(config, &items)
        .into_iter()
        .map(HomeShelfDto::from)
        .collect();
    let titles: Vec<CatalogTitle> = items
        .iter()
        .map(|item| {
            CatalogTitle::from_item(
                item,
                CatalogTitle::progress_for_item(item, config),
                None,
            )
        })
        .collect();
    let counts = count_by_kind(&items);
    if items.is_empty() && config.media_dirs().is_empty() && !config.source_enabled("steam") {
        errors.push(ScanError {
            source: "Library".into(),
            message: "No sources enabled or folders configured.".into(),
        });
    }
    (
        LibrarySnapshot {
            shelves,
            titles,
            counts,
            errors,
            fingerprint,
        },
        launch_by_id,
        items_by_id,
    )
}
