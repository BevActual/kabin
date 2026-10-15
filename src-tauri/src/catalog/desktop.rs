use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};

use regex::Regex;

use super::item::LibraryItem;
use super::launch::LaunchPlan;

const EXCLUDED_IDS: [&str; 26] = [
    "steam.desktop",
    "kabin.desktop",
    "omagames.desktop",
    "io.mgba.mGBA.desktop",
    "org.duckstation.DuckStation.desktop",
    "net.pcsx2.PCSX2.desktop",
    "org.ppsspp.PPSSPP.desktop",
    "org.DolphinEmu.dolphin-emu.desktop",
    "dolphin-emu.desktop",
    "com.snes9x.Snes9x.desktop",
    "org.mamedev.MAME.desktop",
    "mame.desktop",
    "com.libretro.RetroArch.desktop",
    "com.github.Rosalie241.RMG.desktop",
    "io.github.gopher64.gopher64.desktop",
    "io.github.punesemu.puNES.desktop",
    "org.fceux.fceux.desktop",
    "fceux.desktop",
    "io.github.SourMesen.Mesen.desktop",
    "mesen.desktop",
    "com.moonlight_stream.Moonlight.desktop",
    "com.moonlight-stream.Moonlight.desktop",
    "moonlight.desktop",
    "sunshine.desktop",
    "com.lizardbyte.sunshine.desktop",
    "dev.lizardbyte.app.Sunshine.desktop",
];

fn application_dirs() -> Vec<PathBuf> {
    let mut dirs = Vec::new();
    if let Some(home) = dirs::home_dir() {
        dirs.push(home.join(".local/share/applications"));
    }
    dirs.push(PathBuf::from("/usr/share/applications"));
    dirs.push(PathBuf::from("/usr/local/share/applications"));
    dirs
}

fn parse_desktop_file(path: &Path) -> Option<(String, String, String, bool)> {
    let text = fs::read_to_string(path).ok()?;
    let mut name = String::new();
    let mut exec = String::new();
    let mut categories = String::new();
    let mut no_display = false;
    for line in text.lines() {
        let line = line.trim();
        if line.starts_with("Name=") && name.is_empty() {
            name = line.trim_start_matches("Name=").trim().to_string();
        } else if line.starts_with("Exec=") && exec.is_empty() {
            exec = line.trim_start_matches("Exec=").trim().to_string();
        } else if line.starts_with("Categories=") {
            categories = line.trim_start_matches("Categories=").trim().to_string();
        } else if line.starts_with("NoDisplay=true") || line.starts_with("Hidden=true") {
            no_display = true;
        }
    }
    if name.is_empty() {
        return None;
    }
    Some((name, exec, categories, no_display))
}

fn is_game_category(categories: &str) -> bool {
    categories.split(';').any(|part| part.eq_ignore_ascii_case("Game"))
}

fn desktop_id(path: &Path) -> String {
    format!(
        "desktop:{}",
        path.file_name().unwrap_or_default().to_string_lossy()
    )
}

fn safe_mtime(path: &Path) -> f64 {
    path.metadata()
        .ok()
        .and_then(|m| m.modified().ok())
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

pub fn scan_desktop(
    hidden: &HashSet<String>,
    steam_appids: &HashSet<String>,
) -> Vec<LibraryItem> {
    let steam_re = Regex::new(r"steam://rungameid/(\d+)").unwrap();
    let mut games = Vec::new();
    for dir in application_dirs() {
        if !dir.is_dir() {
            continue;
        }
        let Ok(read) = fs::read_dir(&dir) else {
            continue;
        };
        for entry in read.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) != Some("desktop") {
                continue;
            }
            let file_name = path.file_name().unwrap_or_default().to_string_lossy();
            if EXCLUDED_IDS
                .iter()
                .any(|id| id.eq_ignore_ascii_case(file_name.as_ref()))
            {
                continue;
            }
            let Some((name, exec, categories, no_display)) = parse_desktop_file(&path) else {
                continue;
            };
            if no_display || !is_game_category(&categories) {
                continue;
            }
            if let Some(caps) = steam_re.captures(&exec) {
                if steam_appids.contains(caps.get(1).map(|m| m.as_str()).unwrap_or("")) {
                    continue;
                }
            }
            let id = desktop_id(&path);
            if hidden.contains(&id) {
                continue;
            }
            games.push(LibraryItem {
                id,
                title: name,
                subtitle: "Installed App".into(),
                kind_id: "game".into(),
                source: "desktop".into(),
                cover_path: None,
                added_at: safe_mtime(&path),
                track_count: 1,
                launch: LaunchPlan::Desktop {
                    desktop_file: path.clone(),
                },
            });
        }
    }
    games
}
