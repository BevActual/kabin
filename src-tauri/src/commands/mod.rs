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

#[tauri::command]
pub fn get_library_counts(
    state: tauri::State<'_, AppState>,
) -> std::collections::HashMap<String, u32> {
    state.snapshot(false).counts
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
