use std::fs;
use std::path::{Path, PathBuf};

use sha2::{Digest, Sha256};

pub fn remote_cache_root() -> PathBuf {
    dirs::cache_dir()
        .unwrap_or_else(|| PathBuf::from(".cache"))
        .join("kabin")
        .join("remote")
}

pub fn cache_path(host_key: &str, remote_id: &str, size: u64, suffix: &str) -> PathBuf {
    let identity = format!("{host_key}\0{remote_id}\0{size}");
    let digest = hex::encode(Sha256::digest(identity.as_bytes()));
    remote_cache_root().join(digest).join(format!(
        "media{}",
        suffix
    ))
}

pub fn ensure_parent(path: &Path) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    Ok(())
}

pub fn write_atomic(path: &Path, bytes: &[u8]) -> Result<(), String> {
    ensure_parent(path)?;
    let tmp = path.with_extension("part");
    fs::write(&tmp, bytes).map_err(|e| e.to_string())?;
    fs::rename(&tmp, path).map_err(|e| e.to_string())?;
    Ok(())
}

pub fn suffix_for_remote_id(remote_id: &str) -> String {
    Path::new(remote_id)
        .extension()
        .map(|e| format!(".{}", e.to_string_lossy()))
        .unwrap_or_else(|| ".bin".into())
}
