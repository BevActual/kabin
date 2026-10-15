use serde::Serialize;
use std::path::Path;

use crate::catalog::systems::{get_system, SYSTEMS};

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
    ("snes", "snes9x", "Snes9x", "snes9x"),
    ("n64", "rmg", "RMG", "RMG"),
    ("gb", "mgba", "mGBA", "mgba-qt"),
    ("gbc", "mgba", "mGBA", "mgba-qt"),
    ("gba", "mgba", "mGBA", "mgba-qt"),
    ("genesis", "blastem", "BlastEm", "blastem"),
    ("ps1", "duckstation", "DuckStation", "duckstation-qt"),
    ("ps2", "pcsx2", "PCSX2", "pcsx2-qt"),
    ("psp", "ppsspp", "PPSSPP", "PPSSPPSDL"),
    ("gamecube", "dolphin", "Dolphin", "dolphin-emu"),
    ("wii", "dolphin", "Dolphin", "dolphin-emu"),
    ("arcade", "mame", "MAME", "mame"),
];

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
        if seen.contains(*eid) {
            continue;
        }
        if let Some(path) = which(exe) {
            seen.insert(*eid);
            choices.push(EmulatorChoiceDto {
                id: (*eid).to_string(),
                name: (*name).to_string(),
                runtime: "native".into(),
                executable: path,
            });
        }
    }
    choices
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
