mod catalog;
mod commands;
mod config;
mod emulators;
mod launch_exec;

use config::AppState;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            commands::get_app_info,
            commands::scan_library,
            commands::get_home_shelves,
            commands::get_library_titles,
            commands::get_title,
            commands::get_library_counts,
            commands::launch_title,
            commands::playback::get_playback_session,
            commands::playback::save_playback_progress,
            commands::settings::get_settings,
            commands::settings::set_source_enabled,
            commands::settings::add_media_dir,
            commands::settings::pick_folder,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
