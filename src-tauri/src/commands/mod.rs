use crate::config::{app_info, sample_home_shelves, sample_library, AppInfo, CatalogTitle, HomeShelf};

#[tauri::command]
pub fn get_app_info() -> AppInfo {
    app_info()
}

#[tauri::command]
pub fn get_home_shelves() -> Vec<HomeShelf> {
    sample_home_shelves()
}

#[tauri::command]
pub fn get_library_titles(kind: String) -> Vec<CatalogTitle> {
    sample_library(&kind)
}
