mod commands;
mod config;

use config::AppState;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            commands::get_app_info,
            commands::get_home_shelves,
            commands::get_library_titles,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
