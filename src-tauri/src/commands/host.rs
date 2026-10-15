use std::sync::Mutex;

use tauri::State;

use crate::config::KabinConfig;
use crate::host::{self, HostController, HostStatus};

pub struct HostHandle(pub Mutex<HostController>);

#[tauri::command]
pub fn get_host_status(host: State<'_, HostHandle>) -> HostStatus {
    let config = KabinConfig::load();
    let controller = host.0.lock().expect("host lock");
    controller.status(&config)
}

#[tauri::command]
pub fn set_host_enabled(
    app_state: State<'_, crate::config::AppState>,
    host: State<'_, HostHandle>,
    enabled: bool,
) -> Result<HostStatus, String> {
    let mut config = KabinConfig::load();
    config.set_host_enabled(enabled);
    config.save()?;
    host::sync_host(&app_state, &host.0);
    let controller = host.0.lock().expect("host lock");
    Ok(controller.status(&KabinConfig::load()))
}

#[tauri::command]
pub fn create_host_pairing_code(
    host: State<'_, HostHandle>,
    lifetime_secs: Option<u64>,
) -> Result<String, String> {
    let controller = host.0.lock().expect("host lock");
    if !controller.is_running() {
        return Err("Kabin Host is not running".into());
    }
    Ok(controller.create_pairing_code(lifetime_secs.unwrap_or(300)))
}
