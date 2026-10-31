use serde::Serialize;
use tauri_plugin_dialog::DialogExt;

use crate::config::{AppState, KabinConfig};

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SettingsSnapshot {
    pub config_path: String,
    pub sources: serde_json::Map<String, serde_json::Value>,
    pub media_dirs: Vec<serde_json::Value>,
    pub rom_dirs: Vec<serde_json::Value>,
    pub bios_paths: serde_json::Map<String, serde_json::Value>,
    pub emulation: serde_json::Value,
    pub connected_controllers: Vec<String>,
}

#[tauri::command]
pub fn get_settings() -> SettingsSnapshot {
    let config = KabinConfig::load();
    SettingsSnapshot {
        config_path: config.path.to_string_lossy().into_owned(),
        sources: config.sources_map(),
        media_dirs: config
            .data
            .get("media_dirs")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default(),
        rom_dirs: config.rom_dirs_raw(),
        bios_paths: config
            .emulation_settings()
            .and_then(|v| v.get("bios"))
            .and_then(|v| v.as_object())
            .cloned()
            .unwrap_or_default(),
        emulation: config
            .emulation_settings()
            .cloned()
            .unwrap_or_else(|| crate::emulators::presets::settings_for_preset("balanced")),
        connected_controllers: crate::emulators::controllers::connected_controllers(),
    }
}

#[tauri::command]
pub fn set_source_enabled(
    state: tauri::State<'_, AppState>,
    key: String,
    enabled: bool,
) -> Result<(), String> {
    let mut config = KabinConfig::load();
    config.set_source_enabled(&key, enabled);
    config.save()?;
    state.invalidate();
    Ok(())
}

#[tauri::command]
pub fn remove_media_dir(
    state: tauri::State<'_, AppState>,
    path: String,
) -> Result<(), String> {
    let mut config = KabinConfig::load();
    config.remove_dir_entry("media_dirs", &path);
    config.save()?;
    state.invalidate();
    Ok(())
}

#[tauri::command]
pub fn remove_rom_dir(
    state: tauri::State<'_, AppState>,
    path: String,
) -> Result<(), String> {
    let mut config = KabinConfig::load();
    config.remove_dir_entry("rom_dirs", &path);
    config.save()?;
    state.invalidate();
    Ok(())
}

#[tauri::command]
pub fn add_media_dir(
    state: tauri::State<'_, AppState>,
    path: String,
    media_type: String,
) -> Result<(), String> {
    let mut config = KabinConfig::load();
    config.add_media_dir(&path, &media_type);
    config.save()?;
    state.invalidate();
    Ok(())
}

#[tauri::command]
pub fn list_emulation_presets() -> Vec<crate::emulators::presets::EmulationPresetDto> {
    crate::emulators::presets::list_presets()
}

#[tauri::command]
pub fn set_emulation_preset(
    state: tauri::State<'_, AppState>,
    preset_id: String,
) -> Result<serde_json::Value, String> {
    let mut config = KabinConfig::load();
    crate::emulators::presets::apply_preset_to_config(&mut config, &preset_id);
    let settings = config.emulation_settings().cloned().unwrap_or_default();
    config.save()?;
    state.invalidate();
    Ok(settings)
}

#[tauri::command]
pub fn list_systems() -> Vec<crate::emulators::detect::SystemInfo> {
    crate::emulators::detect::list_systems()
}

#[tauri::command]
pub fn list_emulators(system_id: String) -> Vec<crate::emulators::detect::EmulatorChoiceDto> {
    crate::emulators::detect::detect_emulators(&system_id)
}

#[tauri::command]
pub fn recommended_managed_runtime(
    system_id: String,
) -> Option<crate::emulators::detect::ManagedRuntimeDto> {
    crate::emulators::detect::recommended_managed_runtime(&system_id)
}

#[tauri::command]
pub async fn install_managed_runtime(runtime_id: String) -> Result<String, String> {
    let spec = crate::emulators::managed::runtime_by_id(&runtime_id)
        .ok_or_else(|| format!("Unknown managed runtime: {runtime_id}"))?;
    let spec = *spec;
    tauri::async_runtime::spawn_blocking(move || {
        crate::emulators::managed::install_runtime(&spec)
            .map(|path| path.to_string_lossy().into_owned())
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
pub fn add_rom_dir_custom(
    state: tauri::State<'_, AppState>,
    path: String,
    system_id: String,
    command_template: String,
) -> Result<(), String> {
    if !command_template.contains("{rom}") {
        return Err("Custom emulator command must include {rom}".into());
    }
    let extensions = crate::emulators::detect::default_extensions(&system_id);
    let mut config = KabinConfig::load();
    config.add_rom_dir(
        &path,
        &system_id,
        serde_json::json!(command_template),
        extensions,
    );
    config.save()?;
    state.invalidate();
    Ok(())
}

#[tauri::command]
pub fn add_rom_dir(
    state: tauri::State<'_, AppState>,
    path: String,
    system_id: String,
    emulator_id: String,
    executable: String,
    runtime: String,
) -> Result<(), String> {
    let choice = crate::emulators::detect::EmulatorChoiceDto {
        id: emulator_id,
        name: executable.clone(),
        runtime,
        executable,
    };
    let extensions = crate::emulators::detect::default_extensions(&system_id);
    let mut config = KabinConfig::load();
    config.add_rom_dir(
        &path,
        &system_id,
        crate::emulators::detect::emulator_to_config(&choice),
        extensions,
    );
    config.save()?;
    state.invalidate();
    Ok(())
}

#[tauri::command]
pub fn set_system_bios_path(system_id: String, path: String) -> Result<(), String> {
    let mut config = KabinConfig::load();
    if !crate::emulators::detect::validate_bios_folder(&path) {
        return Err("Choose a folder that contains .bin or .rom firmware files".into());
    }
    let root = config
        .data
        .as_object_mut()
        .expect("config root")
        .entry("emulation")
        .or_insert_with(|| serde_json::json!({}));
    if let Some(obj) = root.as_object_mut() {
        let bios = obj.entry("bios").or_insert_with(|| serde_json::json!({}));
        if let Some(map) = bios.as_object_mut() {
            map.insert(system_id, serde_json::json!(path));
        }
    }
    config.save()
}

#[tauri::command]
pub async fn pick_folder(app: tauri::AppHandle) -> Option<String> {
    app.dialog()
        .file()
        .set_title("Choose folder")
        .blocking_pick_folder()
        .map(|path| path.to_string())
}
