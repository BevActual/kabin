use std::path::{Path, PathBuf};
use std::process::Command;

pub fn open_path(path: &str) -> Result<(), String> {
    #[cfg(windows)]
    {
        Command::new("cmd")
            .args(["/C", "start", "", path])
            .spawn()
            .map_err(|e| format!("Could not open file: {e}"))?;
        return Ok(());
    }
    #[cfg(not(windows))]
    {
        Command::new("xdg-open")
            .arg(path)
            .spawn()
            .map_err(|e| format!("Could not open file: {e}"))?;
        Ok(())
    }
}

pub fn spawn_steam_game(appid: &str) -> Result<(), String> {
    let url = format!("steam://rungameid/{appid}");
    #[cfg(windows)]
    {
        if let Some(exe) = locate_steam_exe() {
            Command::new(exe)
                .arg(&url)
                .spawn()
                .map_err(|e| format!("Could not start Steam: {e}"))?;
            return Ok(());
        }
        return open_path(&url);
    }
    #[cfg(not(windows))]
    {
        Command::new("steam")
            .arg(url)
            .spawn()
            .map_err(|e| format!("Could not start Steam: {e}"))?;
        Ok(())
    }
}

pub fn find_on_path(names: &[&str]) -> Option<PathBuf> {
    for name in names {
        if let Some(found) = which_command(name) {
            return Some(found);
        }
        #[cfg(windows)]
        if !name.to_ascii_lowercase().ends_with(".exe") {
            if let Some(found) = which_command(&format!("{name}.exe")) {
                return Some(found);
            }
        }
    }
    #[cfg(windows)]
    {
        for name in names {
            let file = if name.to_ascii_lowercase().ends_with(".exe") {
                (*name).to_string()
            } else {
                format!("{name}.exe")
            };
            if let Some(found) = search_program_dirs(&file) {
                return Some(found);
            }
        }
    }
    None
}

pub fn is_executable(path: &Path) -> bool {
    if !path.is_file() {
        return false;
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        return path
            .metadata()
            .map(|meta| meta.permissions().mode() & 0o111 != 0)
            .unwrap_or(false);
    }
    #[cfg(not(unix))]
    {
        true
    }
}

pub fn make_user_executable(path: &Path) -> Result<(), String> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o755))
            .map_err(|e| e.to_string())?;
    }
    #[cfg(not(unix))]
    {
        let _ = path;
    }
    Ok(())
}

pub fn link_or_copy(source: &Path, target: &Path) {
    #[cfg(unix)]
    {
        let _ = std::os::unix::fs::symlink(source, target);
    }
    #[cfg(windows)]
    {
        if std::os::windows::fs::symlink_file(source, target).is_err() {
            let _ = std::fs::copy(source, target);
        }
    }
}

pub fn split_command(template: &str) -> Result<Vec<String>, String> {
    #[cfg(windows)]
    {
        split_windows_command(template)
    }
    #[cfg(not(windows))]
    {
        shell_words::split(template).map_err(|e| e.to_string())
    }
}

pub fn expand_user_path(raw: &str) -> PathBuf {
    let trimmed = raw.trim();
    if let Some(rest) = trimmed.strip_prefix('~') {
        let rest = rest.trim_start_matches(['/', '\\']);
        if let Some(home) = dirs::home_dir() {
            return if rest.is_empty() {
                home
            } else {
                home.join(rest)
            };
        }
    }
    PathBuf::from(trimmed)
}

#[cfg_attr(not(windows), allow(dead_code))]
pub fn split_windows_command(input: &str) -> Result<Vec<String>, String> {
    let mut args = Vec::new();
    let mut current = String::new();
    let mut in_quotes = false;
    for c in input.chars() {
        match c {
            '"' => in_quotes = !in_quotes,
            ' ' | '\t' if !in_quotes => {
                if !current.is_empty() {
                    args.push(std::mem::take(&mut current));
                }
            }
            _ => current.push(c),
        }
    }
    if in_quotes {
        return Err("Unclosed quote in emulator command".into());
    }
    if !current.is_empty() {
        args.push(current);
    }
    Ok(args)
}

#[cfg_attr(not(windows), allow(dead_code))]
pub fn parse_reg_steam_path(text: &str) -> Option<String> {
    for line in text.lines() {
        let line = line.trim();
        let Some(rest) = line.strip_prefix("SteamPath") else {
            continue;
        };
        let rest = rest.trim().strip_prefix("REG_SZ")?.trim();
        if !rest.is_empty() {
            return Some(rest.to_string());
        }
    }
    None
}

fn which_command(name: &str) -> Option<PathBuf> {
    #[cfg(windows)]
    let mut command = {
        let mut command = Command::new("where");
        command.arg(name);
        command
    };
    #[cfg(not(windows))]
    let mut command = {
        let mut command = Command::new("which");
        command.arg(name);
        command
    };
    let output = command.output().ok()?;
    if !output.status.success() {
        return None;
    }
    let text = String::from_utf8(output.stdout).ok()?;
    let first = text.lines().find(|line| !line.trim().is_empty())?;
    let path = PathBuf::from(first.trim());
    if path.as_os_str().is_empty() {
        None
    } else {
        Some(path)
    }
}

#[cfg(windows)]
fn locate_steam_exe() -> Option<PathBuf> {
    if let Some(root) = steam_root_from_registry() {
        let exe = root.join("steam.exe");
        if exe.is_file() {
            return Some(exe);
        }
    }
    for root in steam_install_roots() {
        let exe = root.join("steam.exe");
        if exe.is_file() {
            return Some(exe);
        }
    }
    find_on_path(&["steam.exe"])
}

#[cfg(windows)]
pub fn steam_install_roots() -> Vec<PathBuf> {
    let mut roots = Vec::new();
    if let Some(root) = steam_root_from_registry() {
        roots.push(root);
    }
    for key in ["ProgramFiles(x86)", "ProgramFiles"] {
        if let Some(value) = std::env::var_os(key) {
            roots.push(PathBuf::from(value).join("Steam"));
        }
    }
    roots
}

#[cfg(not(windows))]
pub fn steam_install_roots() -> Vec<PathBuf> {
    let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
    vec![
        home.join(".local/share/Steam"),
        home.join(".steam/steam"),
        home.join(".steam/root"),
    ]
}

#[cfg(windows)]
fn steam_root_from_registry() -> Option<PathBuf> {
    let output = Command::new("reg")
        .args(["query", r"HKCU\Software\Valve\Steam", "/v", "SteamPath"])
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let text = String::from_utf8(output.stdout).ok()?;
    parse_reg_steam_path(&text).map(PathBuf::from)
}

#[cfg(windows)]
fn search_program_dirs(file_name: &str) -> Option<PathBuf> {
    let mut roots = Vec::new();
    for key in ["ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"] {
        if let Some(value) = std::env::var_os(key) {
            roots.push(PathBuf::from(value));
        }
    }
    for root in roots {
        let direct = root.join(file_name);
        if direct.is_file() {
            return Some(direct);
        }
        let Ok(entries) = std::fs::read_dir(&root) else {
            continue;
        };
        for entry in entries.flatten().take(500) {
            let dir = entry.path();
            if !dir.is_dir() {
                continue;
            }
            let candidate = dir.join(file_name);
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::{parse_reg_steam_path, split_windows_command};

    #[test]
    fn windows_command_keeps_backslashes() {
        let parts = split_windows_command(
            r#""C:\Program Files\PCSX2\pcsx2-qt.exe" -batch "{rom}""#,
        )
        .unwrap();
        assert_eq!(
            parts,
            vec![
                r"C:\Program Files\PCSX2\pcsx2-qt.exe",
                "-batch",
                "{rom}",
            ]
        );
    }

    #[test]
    fn reads_steam_path_from_reg_query() {
        let sample = "\nHKEY_CURRENT_USER\\Software\\Valve\\Steam\n    SteamPath    REG_SZ    C:/Program Files (x86)/Steam\n";
        assert_eq!(
            parse_reg_steam_path(sample).as_deref(),
            Some("C:/Program Files (x86)/Steam")
        );
    }
}
