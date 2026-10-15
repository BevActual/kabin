use std::path::{Path, PathBuf};

const IMAGE_SUFFIXES: [&str; 4] = [".jpg", ".jpeg", ".png", ".webp"];

pub fn local_cover(path: &Path) -> Option<PathBuf> {
    let parent = path.parent()?;
    for suffix in IMAGE_SUFFIXES {
        let sidecar = path.with_extension(suffix.trim_start_matches('.'));
        if sidecar.is_file() {
            return Some(sidecar);
        }
    }
    let stem = path.file_stem()?.to_string_lossy();
    for subdir in ["covers", "media"] {
        let folder = parent.join(subdir);
        if !folder.is_dir() {
            continue;
        }
        for suffix in IMAGE_SUFFIXES {
            let candidate = folder.join(format!("{stem}{suffix}"));
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    None
}

pub fn folder_cover(directory: &Path) -> Option<PathBuf> {
    if !directory.is_dir() {
        return None;
    }
    for name in ["cover", "folder", "front", "album", "poster"] {
        for suffix in IMAGE_SUFFIXES {
            let candidate = directory.join(format!("{name}{suffix}"));
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    None
}
