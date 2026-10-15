use crate::catalog::playback::{build_playback_session, PlaybackSession};
use crate::config::{AppState, KabinConfig};

#[tauri::command]
pub fn get_playback_session(
    state: tauri::State<'_, AppState>,
    title_id: String,
) -> Option<PlaybackSession> {
    let _snapshot = state.snapshot(false);
    let item = state.find_item(&title_id)?;
    build_playback_session(&item, &KabinConfig::load())
}

#[tauri::command]
pub fn save_playback_progress(
    state: tauri::State<'_, AppState>,
    title_id: String,
    position: f64,
    duration: f64,
    track: u32,
) -> Result<(), String> {
    let mut config = KabinConfig::load();
    config.save_progress(&title_id, position, duration, track)?;
    if let Some(item) = state.find_item(&title_id) {
        let config = KabinConfig::load();
        let item = item.clone();
        std::thread::spawn(move || {
            crate::remote::push_playback_to_host(&config, &item, position, duration, track);
        });
    }
    Ok(())
}
