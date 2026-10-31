use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};

#[cfg(not(windows))]
use regex::Regex;

use super::item::LibraryItem;
use super::launch::LaunchPlan;

#[cfg(not(windows))]
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

#[cfg(not(windows))]
fn application_dirs() -> Vec<PathBuf> {
    let mut dirs = Vec::new();
    if let Some(home) = dirs::home_dir() {
        dirs.push(home.join(".local/share/applications"));
    }
    dirs.push(PathBuf::from("/usr/share/applications"));
    dirs.push(PathBuf::from("/usr/local/share/applications"));
    dirs
}

#[cfg(not(windows))]
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

#[cfg(not(windows))]
fn is_game_category(categories: &str) -> bool {
    categories.split(';').any(|part| part.eq_ignore_ascii_case("Game"))
}

#[cfg(not(windows))]
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
    #[cfg(windows)]
    {
        return scan_start_menu(hidden, steam_appids);
    }
    #[cfg(not(windows))]
    {
        scan_desktop_files(hidden, steam_appids)
    }
}

#[cfg(not(windows))]
fn scan_desktop_files(
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
                host_progress: None,
                series: String::new(),
                series_index: None,
                creators: Vec::new(),
            });
        }
    }
    games
}

#[cfg_attr(not(windows), allow(dead_code))]
pub fn windows_shortcut_is_game(name: &str, link: &str, target: &str) -> bool {
    let name_l = name.to_lowercase();
    if name_l.contains("uninstall")
        || name_l.contains("readme")
        || name_l.contains("website")
        || name_l.contains("help")
    {
        return false;
    }
    let target_l = target.to_lowercase();
    if target_l.ends_with("steam.exe")
        || target_l.contains("steamapps")
        || target_l.ends_with("uninstall.exe")
        || target_l.ends_with("unins000.exe")
    {
        return false;
    }
    let blob = format!("{name_l}\n{}\n{target_l}", link.to_lowercase());
    const MARKERS: &[&str] = &[
        "\\gog games\\",
        "\\gog galaxy\\games\\",
        "/gog games/",
        "\\epic games\\",
        "/epic games/",
        "\\xboxgames\\",
        "\\games\\",
        "/games/",
    ];
    MARKERS.iter().any(|marker| blob.contains(marker))
}

#[cfg(windows)]
fn scan_start_menu(
    hidden: &HashSet<String>,
    _steam_appids: &HashSet<String>,
) -> Vec<LibraryItem> {
    let output = std::process::Command::new("powershell")
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            r#"
$shell = New-Object -ComObject WScript.Shell
$roots = @(
  [Environment]::GetFolderPath('StartMenu'),
  [Environment]::GetFolderPath('CommonStartMenu')
)
foreach ($root in $roots) {
  if (-not (Test-Path $root)) { continue }
  Get-ChildItem -Path $root -Filter *.lnk -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
    try {
      $shortcut = $shell.CreateShortcut($_.FullName)
      $target = $shortcut.TargetPath
      if ($target) {
        Write-Output ($_.BaseName + [char]31 + $_.FullName + [char]31 + $target)
      }
    } catch {}
  }
}
"#,
        ])
        .output();
    let Ok(output) = output else {
        return Vec::new();
    };
    if !output.status.success() {
        return Vec::new();
    }
    let text = String::from_utf8_lossy(&output.stdout);
    let mut games = Vec::new();
    for line in text.lines() {
        let mut parts = line.split('\u{1f}');
        let Some(name) = parts.next() else { continue };
        let Some(link) = parts.next() else { continue };
        let Some(target) = parts.next() else { continue };
        if !windows_shortcut_is_game(name, link, target) {
            continue;
        }
        let path = PathBuf::from(link);
        let id = format!("desktop:{}", link.replace('\\', "/"));
        if hidden.contains(&id) {
            continue;
        }
        games.push(LibraryItem {
            id,
            title: name.to_string(),
            subtitle: "Installed App".into(),
            kind_id: "game".into(),
            source: "desktop".into(),
            cover_path: None,
            added_at: safe_mtime(&path),
            track_count: 1,
            launch: LaunchPlan::Desktop {
                desktop_file: path,
            },
            host_progress: None,
            series: String::new(),
            series_index: None,
            creators: Vec::new(),
        });
    }
    games
}

#[cfg(test)]
mod tests {
    use super::windows_shortcut_is_game;

    #[test]
    fn keeps_gog_and_start_menu_games() {
        assert!(windows_shortcut_is_game(
            "Hades",
            r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Games\Hades.lnk",
            r"D:\Games\Hades\Hades.exe",
        ));
        assert!(windows_shortcut_is_game(
            "Control",
            r"C:\Users\Ada\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Control.lnk",
            r"C:\Program Files\GOG Galaxy\Games\Control\Control.exe",
        ));
    }

    #[test]
    fn skips_steam_and_uninstallers() {
        assert!(!windows_shortcut_is_game(
            "Hades",
            r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Games\Hades.lnk",
            r"D:\Steam\steamapps\common\Hades\Hades.exe",
        ));
        assert!(!windows_shortcut_is_game(
            "Uninstall Hades",
            r"C:\Games\Hades\Uninstall.lnk",
            r"C:\Games\Hades\uninstall.exe",
        ));
    }
}
