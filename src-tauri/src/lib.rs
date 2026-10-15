mod catalog;
mod commands;
mod config;
mod emulators;
mod host;
mod launch_exec;
mod launch_session;
mod media_helper;
mod remote;
mod sessions;

use std::sync::Mutex;

use tauri::Manager;

use commands::host::HostHandle;
use config::AppState;
use host::HostController;
use launch_session::LaunchSessionState;
use remote::game_stream::RemoteGameStreamState;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(AppState::default())
        .manage(LaunchSessionState::default())
        .manage(RemoteGameStreamState::default())
        .manage(HostHandle(Mutex::new(HostController::default())))
        .setup(|app| {
            let state = app.state::<AppState>().inner().clone();
            let host = app.state::<HostHandle>();
            host::sync_host(&state, &host.0);
            Ok(())
        })
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
            commands::reader::get_reader_session,
            commands::reader::save_reader_progress,
            commands::settings::list_emulation_presets,
            commands::settings::set_emulation_preset,
            commands::settings::list_systems,
            commands::settings::list_emulators,
            commands::settings::recommended_managed_runtime,
            commands::settings::install_managed_runtime,
            commands::settings::add_rom_dir,
            commands::settings::get_settings,
            commands::settings::set_source_enabled,
            commands::settings::add_media_dir,
            commands::settings::pick_folder,
            commands::settings::set_system_bios_path,
            commands::open::open_external_path,
            commands::host::get_host_status,
            commands::host::set_host_enabled,
            commands::host::create_host_pairing_code,
            commands::remote::discover_nearby_kabin_hosts,
            commands::remote::list_remote_hosts,
            commands::remote::pair_remote_host,
            commands::remote::remove_remote_host,
            commands::remote::remote_game_stream_available,
            commands::remote::start_remote_game_stream,
            commands::remote::stop_remote_game_stream,
            commands::remote::remote_game_stream_status,
            commands::get_related_titles,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
