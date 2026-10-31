use std::path::{Path, PathBuf};
use std::process::Command;

use super::reader::reader_cache_root;

fn archive_tool() -> Option<&'static str> {
    if command_ok("bsdtar") {
        return Some("bsdtar");
    }
    // Windows ships libarchive as tar.exe, which can read rar/7z comics.
    #[cfg(windows)]
    if command_ok("tar") {
        return Some("tar");
    }
    None
}

fn command_ok(name: &str) -> bool {
    Command::new(name)
        .arg("--version")
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

pub fn bsdtar_available() -> bool {
    archive_tool().is_some()
}

fn bsdtar_pattern(member: &str) -> String {
    member.replace('[', "[[]")
}

fn is_comic_image(name: &str) -> bool {
    let lower = name.to_lowercase();
    lower.ends_with(".png")
        || lower.ends_with(".jpg")
        || lower.ends_with(".jpeg")
        || lower.ends_with(".webp")
        || lower.ends_with(".gif")
}

pub fn extract_bsdtar_comic(archive: &Path, title_id: &str) -> Result<Vec<PathBuf>, String> {
    let Some(tool) = archive_tool() else {
        return Err("bsdtar is required for CBR/CBT/CB7 comics".into());
    };
    let out = reader_cache_root(title_id);
    let manifest = out.join(".manifest");
    if manifest.is_file() {
        let list = std::fs::read_to_string(&manifest).map_err(|e| e.to_string())?;
        let paths: Vec<PathBuf> = list
            .lines()
            .filter(|l| !l.is_empty())
            .map(PathBuf::from)
            .filter(|p| p.is_file())
            .collect();
        if !paths.is_empty() {
            return Ok(paths);
        }
    }
    let listing = Command::new(tool)
        .args(["-tf", &archive.to_string_lossy()])
        .output()
        .map_err(|e| e.to_string())?;
    if !listing.status.success() {
        return Err("Could not read comic archive".into());
    }
    let mut names: Vec<String> = String::from_utf8_lossy(&listing.stdout)
        .lines()
        .filter(|line| is_comic_image(line))
        .map(str::to_string)
        .collect();
    names.sort_by(|a, b| a.to_lowercase().cmp(&b.to_lowercase()));
    if names.is_empty() {
        return Err("No images found in comic archive".into());
    }
    std::fs::create_dir_all(&out).map_err(|e| e.to_string())?;
    let mut paths = Vec::new();
    for (index, name) in names.iter().enumerate() {
        let output = Command::new(tool)
            .args([
                "-xOf",
                &archive.to_string_lossy(),
                &bsdtar_pattern(name),
            ])
            .output()
            .map_err(|e| e.to_string())?;
        if !output.status.success() {
            continue;
        }
        let dest = out.join(format!("page-{index:04}.img"));
        std::fs::write(&dest, &output.stdout).map_err(|e| e.to_string())?;
        paths.push(dest);
    }
    if paths.is_empty() {
        return Err("Could not extract comic pages".into());
    }
    std::fs::write(
        &manifest,
        paths
            .iter()
            .map(|p| p.to_string_lossy())
            .collect::<Vec<_>>()
            .join("\n"),
    )
    .map_err(|e| e.to_string())?;
    Ok(paths)
}
