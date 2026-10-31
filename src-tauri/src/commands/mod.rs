pub mod downloads;
pub mod host;
pub mod open;
pub mod playback;
pub mod remote;
pub mod reader;
pub mod settings;

use crate::catalog::{CatalogTitle, HomeShelfDto, LibrarySnapshot};
use crate::config::{app_info, AppInfo, AppState, KabinConfig};
use crate::launch_exec::{execute, LaunchExecution};
use crate::launch_session::LaunchSessionState;

#[tauri::command]
pub fn get_app_info() -> AppInfo {
    app_info()
}

#[tauri::command]
pub fn scan_library(state: tauri::State<'_, AppState>, force: Option<bool>) -> LibrarySnapshot {
    state.snapshot(force.unwrap_or(false))
}

#[tauri::command]
pub fn get_home_shelves(state: tauri::State<'_, AppState>) -> Vec<HomeShelfDto> {
    state.snapshot(false).shelves
}

#[tauri::command]
pub fn get_library_titles(
    state: tauri::State<'_, AppState>,
    kind: String,
) -> Vec<CatalogTitle> {
    let config = KabinConfig::load();
    if kind == "favorites" {
        let favorite_ids: std::collections::HashSet<_> =
            config.favorite_ids().into_iter().collect();
        return state
            .snapshot(false)
            .titles
            .into_iter()
            .filter(|title| favorite_ids.contains(&title.id))
            .collect();
    }
    state
        .snapshot(false)
        .titles
        .into_iter()
        .filter(|title| title.kind == kind)
        .collect()
}

#[tauri::command]
pub fn get_title(state: tauri::State<'_, AppState>, title_id: String) -> Option<CatalogTitle> {
    state
        .snapshot(false)
        .titles
        .into_iter()
        .find(|title| title.id == title_id)
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RelatedShelfDto {
    pub heading: String,
    pub titles: Vec<CatalogTitle>,
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TitleDetailsDto {
    pub title: CatalogTitle,
    pub meta_lines: Vec<String>,
    pub is_favorite: bool,
}

#[tauri::command]
pub fn get_title_details(
    state: tauri::State<'_, AppState>,
    title_id: String,
) -> Option<TitleDetailsDto> {
    let config = KabinConfig::load();
    let item = state.find_item(&title_id)?;
    let title = CatalogTitle::from_item_with_config(
        &item,
        CatalogTitle::progress_for_item(&item, &config),
        None,
        Some(&config),
    );
    Some(TitleDetailsDto {
        meta_lines: crate::catalog::detail_meta::detail_lines(&item),
        is_favorite: config.is_favorite(&title_id),
        title,
    })
}

#[tauri::command]
pub fn toggle_favorite(
    state: tauri::State<'_, AppState>,
    title_id: String,
) -> Result<bool, String> {
    let mut config = KabinConfig::load();
    let is_favorite = config.toggle_favorite(&title_id);
    config.save()?;
    state.invalidate();
    Ok(is_favorite)
}

#[tauri::command]
pub fn search_library(
    state: tauri::State<'_, AppState>,
    query: String,
    limit: Option<usize>,
) -> Vec<CatalogTitle> {
    let config = KabinConfig::load();
    let snapshot = state.snapshot(false);
    let items: Vec<_> = snapshot
        .titles
        .iter()
        .filter_map(|t| state.find_item(&t.id))
        .collect();
    crate::catalog::search::search_titles(&items, &config, &query, limit.unwrap_or(48))
}

#[tauri::command]
pub fn get_related_titles(
    state: tauri::State<'_, AppState>,
    title_id: String,
) -> RelatedShelfDto {
    let config = KabinConfig::load();
    let snapshot = state.snapshot(false);
    let items: Vec<_> = snapshot
        .titles
        .iter()
        .filter_map(|t| state.find_item(&t.id))
        .collect();
    let Some(item) = state.find_item(&title_id) else {
        return RelatedShelfDto {
            heading: String::new(),
            titles: Vec::new(),
        };
    };
    let shelf = crate::catalog::related::related_shelf(&item, &items, &config);
    RelatedShelfDto {
        heading: shelf.heading,
        titles: shelf.titles,
    }
}

#[tauri::command]
pub fn get_library_counts(
    state: tauri::State<'_, AppState>,
) -> std::collections::HashMap<String, u32> {
    let snapshot = state.snapshot(false);
    let mut counts = snapshot.counts;
    let config = KabinConfig::load();
    let favorite_ids: std::collections::HashSet<_> =
        config.favorite_ids().into_iter().collect();
    let favorites = snapshot
        .titles
        .iter()
        .filter(|title| favorite_ids.contains(&title.id))
        .count() as u32;
    counts.insert("favorites".into(), favorites);
    counts
}

#[tauri::command]
pub fn launch_title(
    app: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
    sessions: tauri::State<'_, LaunchSessionState>,
    title_id: String,
) -> Result<(), String> {
    if sessions.is_active() {
        return Err("A game is already running. Quit the emulator before launching another.".into());
    }
    let plan = state
        .launch_plan(&title_id)
        .ok_or_else(|| "Title not found or not launchable".to_string())?;
    let title = state
        .find_item(&title_id)
        .map(|item| item.title)
        .unwrap_or_else(|| title_id.clone());
    let outcome = execute(&plan)?;
    let mut config = KabinConfig::load();
    config.record_played(&title_id);
    config.save()?;
    match outcome {
        LaunchExecution::Detached => {}
        LaunchExecution::Tracked(child) => {
            sessions.start_monitor(app, state.inner().clone(), title_id, title, child);
        }
    }
    state.invalidate();
    Ok(())
}
