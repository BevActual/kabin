use std::fs;
use std::path::{Path, PathBuf};

const VIDEO_EXTENSIONS: &[&str] = &["mkv", "mp4", "m4v", "avi", "webm", "mov"];

pub fn import_videos(source: &Path, import_dir: &Path) -> Result<Vec<PathBuf>, String> {
    if import_dir.as_os_str().is_empty() {
        return Ok(Vec::new());
    }
    if !import_dir.is_dir() {
        return Err("Choose a library folder in Settings before importing".into());
    }
    if same_place(source, import_dir) {
        return Ok(vec![import_dir.to_path_buf()]);
    }
    fs::create_dir_all(import_dir).map_err(|e| e.to_string())?;
    let mut imported = Vec::new();
    if source.is_file() {
        if let Some(target) = place_video(source, import_dir)? {
            imported.push(target);
        }
        return Ok(imported);
    }
    if !source.exists() {
        return Err("Download folder is missing".into());
    }
    visit(source, import_dir, &mut imported)?;
    Ok(imported)
}

fn visit(dir: &Path, import_dir: &Path, imported: &mut Vec<PathBuf>) -> Result<(), String> {
    let entries = fs::read_dir(dir).map_err(|e| e.to_string())?;
    for entry in entries {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        if is_ignored(&path) {
            continue;
        }
        if path.is_dir() {
            visit(&path, import_dir, imported)?;
        } else if let Some(target) = place_video(&path, import_dir)? {
            imported.push(target);
        }
    }
    Ok(())
}

fn place_video(source: &Path, import_dir: &Path) -> Result<Option<PathBuf>, String> {
    if !is_video(source) || is_ignored(source) {
        return Ok(None);
    }
    let name = source
        .file_name()
        .ok_or_else(|| "Video is missing a file name".to_string())?;
    let target = import_dir.join(name);
    if same_place(source, &target) {
        return Ok(Some(target));
    }
    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    if target.exists() {
        return Ok(Some(target));
    }
    if fs::hard_link(source, &target).is_err() {
        fs::copy(source, &target).map_err(|e| format!("Could not import video: {e}"))?;
    }
    Ok(Some(target))
}

fn is_video(path: &Path) -> bool {
    path.extension()
        .and_then(|ext| ext.to_str())
        .map(|ext| {
            VIDEO_EXTENSIONS
                .iter()
                .any(|candidate| candidate.eq_ignore_ascii_case(ext))
        })
        .unwrap_or(false)
}

fn is_ignored(path: &Path) -> bool {
    path.components().any(|component| {
        let text = component.as_os_str().to_string_lossy().to_ascii_lowercase();
        text.starts_with('.') || text.contains("sample")
    })
}

fn same_place(left: &Path, right: &Path) -> bool {
    match (left.canonicalize(), right.canonicalize()) {
        (Ok(left), Ok(right)) => left == right,
        _ => left == right,
    }
}

pub fn format_bytes(bytes: u64) -> String {
    const UNITS: [&str; 5] = ["B", "KB", "MB", "GB", "TB"];
    let mut value = bytes as f64;
    let mut unit = 0;
    while value >= 1000.0 && unit < UNITS.len() - 1 {
        value /= 1000.0;
        unit += 1;
    }
    if unit == 0 {
        format!("{bytes} B")
    } else {
        format!("{value:.1} {}", UNITS[unit])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn imports_video_and_skips_samples() {
        let root = std::env::temp_dir().join(format!("kabin-import-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        let source = root.join("download");
        let library = root.join("movies");
        fs::create_dir_all(source.join("Sample")).unwrap();
        fs::create_dir_all(&library).unwrap();
        fs::write(source.join("Feature.mkv"), b"video").unwrap();
        fs::write(source.join("Sample").join("sample.mkv"), b"sample").unwrap();
        fs::write(source.join("notes.txt"), b"notes").unwrap();

        let imported = import_videos(&source, &library).unwrap();
        assert_eq!(imported.len(), 1);
        assert_eq!(fs::read(library.join("Feature.mkv")).unwrap(), b"video");
        assert!(!library.join("sample.mkv").exists());
        let _ = fs::remove_dir_all(&root);
    }
}
