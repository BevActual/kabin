use std::path::{Path, PathBuf};
use std::process::Command;

use regex::Regex;

use super::item::LibraryItem;
use super::launch::LaunchPlan;

fn default_roots() -> Vec<PathBuf> {
    let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
    vec![
        home.join(".local/share/Steam"),
        home.join(".steam/steam"),
        home.join(".steam/root"),
    ]
}

pub fn find_steam_root(override_path: Option<&str>) -> Option<PathBuf> {
    if let Some(raw) = override_path {
        let path = if raw.starts_with('~') {
            dirs::home_dir().map(|home| home.join(raw.trim_start_matches('~').trim_start_matches('/')))?
        } else {
            PathBuf::from(raw)
        };
        if path.is_dir() {
            return Some(path);
        }
    }
    default_roots()
        .into_iter()
        .find(|candidate| candidate.join("steamapps").is_dir())
}

pub fn parse_vdf(text: &str) -> serde_json::Value {
    let token_re = Regex::new(r#""((?:[^"\\]|\\.)*)"|([{}])"#).unwrap();
    let tokens: Vec<String> = token_re
        .captures_iter(text)
        .filter_map(|cap| {
            cap.get(2)
                .map(|m| m.as_str().to_string())
                .or_else(|| cap.get(1).map(|m| m.as_str().replace("\\\"", "\"")))
        })
        .collect();
    let mut pos = 0;

    fn parse_object(tokens: &[String], pos: &mut usize) -> serde_json::Value {
        let mut map = serde_json::Map::new();
        while *pos < tokens.len() {
            let tok = tokens[*pos].as_str();
            if tok == "}" {
                *pos += 1;
                return serde_json::Value::Object(map);
            }
            let key = tok.to_string();
            *pos += 1;
            if *pos < tokens.len() && tokens[*pos] == "{" {
                *pos += 1;
                map.insert(key, parse_object(tokens, pos));
            } else if *pos < tokens.len() {
                map.insert(key, serde_json::Value::String(tokens[*pos].clone()));
                *pos += 1;
            }
        }
        serde_json::Value::Object(map)
    }

    parse_object(&tokens, &mut pos)
}

fn library_paths(steam_root: &Path) -> Vec<PathBuf> {
    let mut libraries = vec![steam_root.to_path_buf()];
    let vdf_path = steam_root.join("steamapps/libraryfolders.vdf");
    let Ok(text) = std::fs::read_to_string(&vdf_path) else {
        return libraries;
    };
    let data = parse_vdf(&text);
    let root = data.get("libraryfolders").unwrap_or(&data);
    if let Some(obj) = root.as_object() {
        for (_key, entry) in obj {
            if let Some(path) = entry.get("path").and_then(|v| v.as_str()) {
                let lib = PathBuf::from(path);
                if !libraries.iter().any(|l| l == &lib) {
                    libraries.push(lib);
                }
            }
        }
    }
    libraries
}

fn is_real_game(name: &str) -> bool {
    if name.trim().is_empty() {
        return false;
    }
    let re = Regex::new(
        r"(?i)^(Steamworks Common Redistributables|Proton\b.*|Steam Linux Runtime.*|SteamVR.*|Steamworks.*)$",
    )
    .unwrap();
    !re.is_match(name.trim())
}

fn safe_mtime(path: &Path) -> f64 {
    path.metadata()
        .ok()
        .and_then(|m| m.modified().ok())
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

pub fn scan_steam(
    steam_root_override: Option<&str>,
    hidden: &std::collections::HashSet<String>,
) -> Vec<LibraryItem> {
    let Some(steam_root) = find_steam_root(steam_root_override) else {
        return Vec::new();
    };
    let mut games = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for library in library_paths(&steam_root) {
        let steamapps = library.join("steamapps");
        if !steamapps.is_dir() {
            continue;
        }
        let Ok(read) = std::fs::read_dir(&steamapps) else {
            continue;
        };
        for entry in read.flatten() {
            let name = entry.file_name();
            let name = name.to_string_lossy();
            if !name.starts_with("appmanifest_") || !name.ends_with(".acf") {
                continue;
            }
            let Ok(text) = std::fs::read_to_string(entry.path()) else {
                continue;
            };
            let data = parse_vdf(&text);
            let state = data.get("AppState").and_then(|v| v.as_object());
            let Some(state) = state else { continue };
            let appid = state.get("appid").and_then(|v| v.as_str()).unwrap_or("");
            let title = state.get("name").and_then(|v| v.as_str()).unwrap_or("");
            if appid.is_empty() || seen.contains(appid) || !is_real_game(title) {
                continue;
            }
            seen.insert(appid.to_string());
            let id = format!("steam:{appid}");
            if hidden.contains(&id) {
                continue;
            }
            games.push(LibraryItem {
                id,
                title: title.to_string(),
                subtitle: "Steam".into(),
                kind_id: "game".into(),
                source: "steam".into(),
                cover_path: None,
                added_at: safe_mtime(&entry.path()),
                track_count: 1,
                launch: LaunchPlan::Steam {
                    appid: appid.to_string(),
                },
                host_progress: None,
            });
        }
    }
    games
}

#[allow(dead_code)]
pub fn launch_steam(appid: &str) {
    let _ = Command::new("steam")
        .arg(format!("steam://rungameid/{appid}"))
        .spawn();
}

#[cfg(test)]
mod tests {
    use super::parse_vdf;

    #[test]
    fn parses_nested_vdf() {
        let text = r#"
"AppState"
{
    "appid" "570"
    "name" "Dota 2"
}
"#;
        let value = parse_vdf(text);
        let state = value.get("AppState").expect("state");
        assert_eq!(state.get("appid").and_then(|v| v.as_str()), Some("570"));
    }
}
