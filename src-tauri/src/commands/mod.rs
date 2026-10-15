use crate::catalog::{CatalogTitle, HomeShelfDto, LibrarySnapshot};
use crate::config::{app_info, AppInfo, AppState};

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
