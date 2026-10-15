use serde::Serialize;

use crate::config::{KabinConfig, RemoteHostEntry, RemoteHostSummary};
use crate::config::AppState;
use crate::remote::game_stream::RemoteGameStreamState;
use crate::remote::{
    discover_nearby_hosts, fetch_remote_library, game_stream, pair_with_host, DiscoveredHost,
};

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PairRemoteHostResult {
    pub name: String,
    pub item_count: u32,
}

#[tauri::command]
pub fn discover_nearby_kabin_hosts() -> Vec<DiscoveredHost> {
    discover_nearby_hosts(4)
}

#[tauri::command]
pub fn list_remote_hosts() -> Vec<RemoteHostSummary> {
    KabinConfig::load().remote_host_summaries()
}

#[tauri::command]
pub fn pair_remote_host(
    state: tauri::State<'_, AppState>,
    host: RemoteHostEntry,
    code: String,
) -> Result<PairRemoteHostResult, String> {
    let code = code.trim();
    if code.len() != 6 || !code.chars().all(|c| c.is_ascii_digit()) {
        return Err("Enter the six-digit code shown on the host.".into());
    }
    let mut config = KabinConfig::load();
    let device_name = config.host_name();
    let payload = pair_with_host(&host, code, &device_name)?;
    let token = payload
        .get("token")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "Host did not return a token".to_string())?
        .to_string();
    let library = fetch_remote_library(&host, &token)?;
    let count = library
        .get("count")
        .and_then(|v| v.as_u64())
        .unwrap_or(0) as u32;
    config.save_remote_host(host.clone(), token)?;
    state.invalidate();
    Ok(PairRemoteHostResult {
        name: host.name,
        item_count: count,
    })
}

#[tauri::command]
pub fn remove_remote_host(
    state: tauri::State<'_, AppState>,
    name: String,
) -> Result<(), String> {
    let mut config = KabinConfig::load();
    config.remove_remote_host(&name)?;
    state.invalidate();
    Ok(())
}

#[tauri::command]
pub fn remote_game_stream_available() -> bool {
    game_stream::streaming_available()
}

#[tauri::command]
pub fn start_remote_game_stream(
    state: tauri::State<'_, AppState>,
    streams: tauri::State<'_, RemoteGameStreamState>,
    title_id: String,
) -> Result<String, String> {
    streams.start(&state, &title_id)
}

#[tauri::command]
pub fn stop_remote_game_stream(streams: tauri::State<'_, RemoteGameStreamState>) -> Result<(), String> {
    streams.stop();
    Ok(())
}

#[tauri::command]
pub fn remote_game_stream_status(
    streams: tauri::State<'_, RemoteGameStreamState>,
) -> Option<String> {
    streams.active_title()
}
