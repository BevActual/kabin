use std::collections::HashSet;
use std::path::{Path, PathBuf};

use serde_json::Value;

use super::artwork::local_cover;
use super::item::LibraryItem;
use super::launch::LaunchPlan;
use super::systems::get_system;
use super::titles::clean_game_title;
use crate::emulators::{build_command, custom_command};

const SKIP_DIRS: [&str; 6] = ["covers", "media", "images", "manuals", "videos", ".git"];

fn walk_roms(base: &Path, visit: &mut dyn FnMut(&Path)) {
    let mut stack = vec![base.to_path_buf()];
    while let Some(dir) = stack.pop() {
        let Ok(read) = std::fs::read_dir(&dir) else { continue };
        let mut entries: Vec<_> = read.filter_map(Result::ok).collect();
        entries.sort_by_key(|e| e.file_name());
        for entry in entries {
            let path = entry.path();
            if path.is_dir() {
                let name = entry.file_name().to_string_lossy().into_owned();
                if name.starts_with('.') {
                    continue;
                }
                if SKIP_DIRS
                    .iter()
                    .any(|skip| skip.eq_ignore_ascii_case(name.as_ref()))
                {
                    continue;
                }
                stack.push(path);
            } else if path.is_file() {
                visit(&path);
            }
        }
    }
}

fn game_id(system_id: &str, base: &Path, rom_path: &Path) -> String {
    match rom_path.strip_prefix(base) {
        Ok(relative) if relative.parent().is_none_or(|p| p.as_os_str().is_empty()) => {
            format!("roms:{system_id}:{}", rom_path.file_name().unwrap().to_string_lossy())
        }
        Ok(relative) => format!(
            "roms:{system_id}:{}",
            relative.to_string_lossy().replace('\\', "/")
        ),
        Err(_) => format!(
            "roms:{system_id}:{}",
            rom_path.file_name().unwrap().to_string_lossy()
        ),
    }
}

fn safe_mtime(path: &Path) -> f64 {
    path.metadata()
        .ok()
        .and_then(|m| m.modified().ok())
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

fn expand_path(raw: &str) -> PathBuf {
    if raw.starts_with('~') {
        if let Some(home) = dirs::home_dir() {
            return home.join(raw.trim_start_matches('~').trim_start_matches('/'));
        }
    }
    PathBuf::from(raw)
}

fn launch_plan_for_rom(
    emulator: &Value,
    rom_path: &Path,
    emulation_settings: Option<&Value>,
) -> Option<LaunchPlan> {
    if emulator.is_string() {
        let template = emulator.as_str()?;
        let argv = custom_command(template, rom_path).ok()?;
        return Some(LaunchPlan::Command {
            argv,
            emulator_id: None,
            bios_path: None,
        });
    }
    if emulator.is_object() {
        let argv = build_command(emulator, rom_path, emulation_settings).ok()?;
        let emulator_id = emulator
            .get("id")
            .and_then(|v| v.as_str())
            .map(str::to_string);
        return Some(LaunchPlan::Command {
            argv,
            emulator_id,
            bios_path: None,
        });
    }
    None
}

pub fn scan_rom_dirs(
    entries: &[Value],
    hidden: &HashSet<String>,
    emulation_settings: Option<&Value>,
) -> Vec<LibraryItem> {
    let mut games = Vec::new();
    for entry in entries {
        let Some(obj) = entry.as_object() else { continue };
        let path_raw = obj.get("path").and_then(|v| v.as_str()).unwrap_or("");
        let base = expand_path(path_raw);
        if !base.is_dir() {
            continue;
        }
        let system_id = obj
            .get("system")
            .and_then(|v| v.as_str())
            .unwrap_or_else(|| base.file_name().and_then(|n| n.to_str()).unwrap_or("ROMs"));
        let definition = get_system(system_id);
        let system_label = definition.map(|d| d.name).unwrap_or(system_id);
        let mut extensions: HashSet<String> = obj
            .get("extensions")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str())
                    .map(|e| e.trim_start_matches('.').to_lowercase())
                    .collect()
            })
            .unwrap_or_default();
        if let Some(definition) = definition {
            for ext in definition.extensions {
                extensions.insert((*ext).to_string());
            }
        }
        let emulator = obj.get("emulator").cloned().unwrap_or(Value::Null);
        let valid = emulator.is_object()
            || (emulator.is_string() && emulator.as_str().unwrap_or("").contains("{rom}"));
        if !valid {
            continue;
        }

        walk_roms(&base, &mut |rom_path| {
            let ext = rom_path
                .extension()
                .and_then(|e| e.to_str())
                .unwrap_or("")
                .to_lowercase();
            if !extensions.is_empty() && !extensions.contains(&ext) {
                return;
            }
            let id = game_id(system_id, &base, rom_path);
            if hidden.contains(&id) {
                return;
            }
            let Some(mut launch) =
                launch_plan_for_rom(&emulator, rom_path, emulation_settings)
            else {
                return;
            };
            if let LaunchPlan::Command {
                bios_path: ref mut slot,
                ..
            } = &mut launch
            {
                *slot = obj
                    .get("bios_path")
                    .and_then(|v| v.as_str())
                    .map(|raw| expand_path(raw))
                    .filter(|p| p.is_dir());
            }
            let cover = local_cover(rom_path);
            games.push(LibraryItem {
                id,
                title: clean_game_title(&rom_path.file_name().unwrap().to_string_lossy()),
                subtitle: system_label.to_string(),
                kind_id: "game".to_string(),
                source: "roms".to_string(),
                cover_path: cover.map(|p| p.to_string_lossy().into_owned()),
                added_at: safe_mtime(rom_path),
                track_count: 1,
                launch,
                host_progress: None,
            });
        });
    }
    games
}
