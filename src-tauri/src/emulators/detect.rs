use serde::Serialize;
use std::path::{Path, PathBuf};

use crate::catalog::systems::{get_system, SYSTEMS};
use super::managed::{installed_executable, recommended_runtime, RuntimeSpec};

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SystemInfo {
    pub id: String,
    pub name: String,
    pub extensions: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct EmulatorChoiceDto {
    pub id: String,
    pub name: String,
    pub runtime: String,
    pub executable: String,
}

const NATIVE: &[(&str, &str, &str, &str)] = &[
    ("nes", "fceux", "FCEUX", "fceux"),
    ("nes", "mesen", "Mesen", "mesen"),
    ("nes", "punes", "puNES", "punes"),
    ("snes", "snes9x", "Snes9x", "snes9x"),
    ("snes", "mesen", "Mesen", "mesen"),
    ("n64", "rmg", "RMG", "RMG"),
    ("gb", "mgba", "mGBA", "mgba-qt"),
    ("gbc", "mgba", "mGBA", "mgba-qt"),
    ("gba", "mgba", "mGBA", "mgba-qt"),
    ("genesis", "blastem", "BlastEm", "blastem"),
    ("ps1", "duckstation", "DuckStation", "duckstation-qt"),
    ("ps1", "duckstation", "DuckStation", "duckstation"),
    ("ps2", "pcsx2", "PCSX2", "pcsx2-qt"),
    ("ps2", "pcsx2", "PCSX2", "pcsx2"),
    ("psp", "ppsspp", "PPSSPP", "PPSSPPSDL"),
    ("psp", "ppsspp", "PPSSPP", "ppsspp"),
    ("gamecube", "dolphin", "Dolphin", "dolphin-emu"),
    ("wii", "dolphin", "Dolphin", "dolphin-emu"),
    ("arcade", "mame", "MAME", "mame"),
];

const FLATPAK_IDS: &[(&str, &str, &str)] = &[
    ("ps2", "pcsx2", "net.pcsx2.PCSX2"),
    ("psp", "ppsspp", "org.ppsspp.PPSSPP"),
    ("gamecube", "dolphin", "org.DolphinEmu.dolphin-emu"),
    ("wii", "dolphin", "org.DolphinEmu.dolphin-emu"),
];

fn flatpak_installed(app_id: &str) -> bool {
    let home = dirs::home_dir().unwrap_or_else(PathBuf::new);
    [home.join(".local/share/flatpak/app"), PathBuf::from("/var/lib/flatpak/app")]
        .into_iter()
        .any(|root| root.join(app_id).exists())
}

fn flatpak_label(emulator_id: &str) -> &str {
    match emulator_id {
        "dolphin" => "Dolphin",
        "pcsx2" => "PCSX2",
        "ppsspp" => "PPSSPP",
        _ => emulator_id,
    }
}

fn push_managed(
    choices: &mut Vec<EmulatorChoiceDto>,
    seen: &mut std::collections::HashSet<String>,
    emulator_id: &str,
    display_name: &str,
) {
    if seen.contains(emulator_id) {
        return;
    }
    if let Some(path) = installed_executable(emulator_id) {
        seen.insert(emulator_id.to_string());
        choices.push(EmulatorChoiceDto {
            id: emulator_id.to_string(),
            name: format!("{display_name} · Managed by Kabin"),
            runtime: "managed".into(),
            executable: path.to_string_lossy().into_owned(),
        });
    }
}

pub fn list_systems() -> Vec<SystemInfo> {
    SYSTEMS
        .iter()
        .map(|s| SystemInfo {
            id: s.id.to_string(),
            name: s.name.to_string(),
            extensions: s.extensions.iter().map(|e| e.to_string()).collect(),
        })
        .collect()
}

fn which(name: &str) -> Option<String> {
    std::process::Command::new("which")
        .arg(name)
        .output()
        .ok()
        .filter(|o| o.status.success())
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
}

pub fn detect_emulators(system_id: &str) -> Vec<EmulatorChoiceDto> {
    let Some(_system) = get_system(system_id) else {
        return Vec::new();
    };
    let mut choices = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for (sid, eid, name, exe) in NATIVE {
        if *sid != system_id {
            continue;
        }
        push_managed(&mut choices, &mut seen, eid, name);
        if seen.contains(*eid) {
            continue;
        }
        if let Some(path) = which(exe) {
            seen.insert(eid.to_string());
            choices.push(EmulatorChoiceDto {
                id: (*eid).to_string(),
                name: (*name).to_string(),
                runtime: "native".into(),
                executable: path,
            });
        }
    }
    for (sid, eid, app_id) in FLATPAK_IDS {
        if *sid != system_id || seen.contains(*eid) {
            continue;
        }
        if flatpak_installed(app_id) {
            seen.insert(eid.to_string());
            choices.push(EmulatorChoiceDto {
                id: (*eid).to_string(),
                name: flatpak_label(eid).to_string(),
                runtime: "flatpak".into(),
                executable: (*app_id).to_string(),
            });
        }
    }
    choices
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ManagedRuntimeDto {
    pub id: String,
    pub name: String,
}

pub fn recommended_managed_runtime(system_id: &str) -> Option<ManagedRuntimeDto> {
    recommended_runtime(system_id).map(|spec: &RuntimeSpec| ManagedRuntimeDto {
        id: spec.id.to_string(),
        name: spec.name.to_string(),
    })
}

pub fn emulator_to_config(choice: &EmulatorChoiceDto) -> serde_json::Value {
    serde_json::json!({
        "id": choice.id,
        "name": choice.name,
        "runtime": choice.runtime,
        "executable": choice.executable,
    })
}

pub fn default_extensions(system_id: &str) -> Vec<String> {
    get_system(system_id)
        .map(|s| s.extensions.iter().map(|e| e.to_string()).collect())
        .unwrap_or_default()
}

pub fn validate_bios_folder(path: &str) -> bool {
    let path = Path::new(path);
    if !path.is_dir() {
        return false;
    }
    std::fs::read_dir(path)
        .ok()
        .into_iter()
        .flatten()
        .flatten()
        .any(|e| {
            e.path()
                .extension()
                .and_then(|x| x.to_str())
                .is_some_and(|ext| ext.eq_ignore_ascii_case("bin") || ext.eq_ignore_ascii_case("rom"))
        })
}
