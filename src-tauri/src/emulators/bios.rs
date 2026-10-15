use std::fs;
use std::path::{Path, PathBuf};

pub fn firmware_files(bios_path: &Path) -> Vec<PathBuf> {
    let Ok(read) = fs::read_dir(bios_path) else {
        return Vec::new();
    };
    read.flatten()
        .map(|e| e.path())
        .filter(|p| {
            p.is_file()
                && p.extension()
                    .and_then(|e| e.to_str())
                    .is_some_and(|ext| ext.eq_ignore_ascii_case("bin") || ext.eq_ignore_ascii_case("rom"))
        })
        .collect()
}

pub fn prepare_bios_env(emulator_id: &str, bios_path: &Path) -> Option<Vec<(String, String)>> {
    let layout: &[&str] = match emulator_id {
        "duckstation" => &["duckstation", "bios"],
        "pcsx2" => &["PCSX2", "bios"],
        _ => return None,
    };
    let files = firmware_files(bios_path);
    if files.is_empty() {
        return None;
    }
    let data_home = dirs::data_local_dir().unwrap_or_else(|| PathBuf::from(".local/share"));
    let destination = layout.iter().fold(data_home, |acc, segment| acc.join(segment));
    fs::create_dir_all(&destination).ok()?;
    for source in files {
        let target = destination.join(source.file_name()?);
        if target.exists() {
            continue;
        }
        if target.is_symlink() {
            let _ = fs::remove_file(&target);
        }
        let Ok(resolved) = source.canonicalize() else {
            continue;
        };
        #[cfg(unix)]
        {
            let _ = std::os::unix::fs::symlink(resolved, &target);
        }
    }
    None
}
