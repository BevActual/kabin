use std::path::PathBuf;

use sha2::{Digest, Sha256};

use super::cache::{ensure_parent, remote_cache_root, write_atomic};
use super::client::fetch_remote_artwork_bytes;
use crate::catalog::artwork::steam_cached_cover;
use crate::catalog::item::LibraryItem;
use crate::catalog::launch::LaunchPlan;
use crate::config::RemoteHostEntry;

pub fn artwork_cache_path(host_key: &str, remote_id: &str, ext: &str) -> PathBuf {
    let identity = format!("{host_key}\0artwork\0{remote_id}");
    let digest = hex::encode(Sha256::digest(identity.as_bytes()));
    remote_cache_root()
        .join(digest)
        .join(format!("cover{ext}"))
}

pub fn enrich_remote_artwork(host: &RemoteHostEntry, items: &mut [LibraryItem]) {
    let Some(token) = host.token.clone().filter(|t| !t.is_empty()) else {
        return;
    };
    let host_key = format!("{}:{}:{}", host.address, host.port, host.fingerprint);
    for item in items.iter_mut() {
        if item.cover_path.is_some() {
            continue;
        }
        let (fetch, remote_id, appid) = match &item.launch {
            LaunchPlan::RemoteGame {
                has_artwork,
                remote_id,
                appid,
                ..
            } => {
                if !appid.is_empty() {
                    if let Some(path) = steam_cached_cover(appid) {
                        item.cover_path = Some(path.to_string_lossy().into_owned());
                        continue;
                    }
                }
                (*has_artwork, remote_id.clone(), appid.clone())
            }
            LaunchPlan::RemoteStream {
                has_artwork,
                remote_id,
                ..
            } => (*has_artwork, remote_id.clone(), String::new()),
            _ => (false, String::new(), String::new()),
        };
        if !fetch || remote_id.is_empty() {
            let _ = appid;
            continue;
        }
        if let Ok(path) = fetch_and_cache_artwork(host, &host_key, &token, &remote_id) {
            item.cover_path = Some(path.to_string_lossy().into_owned());
        }
    }
}

fn fetch_and_cache_artwork(
    host: &RemoteHostEntry,
    host_key: &str,
    token: &str,
    remote_id: &str,
) -> Result<PathBuf, String> {
    let (bytes, ext) = fetch_remote_artwork_bytes(host, token, remote_id)?;
    let path = artwork_cache_path(host_key, remote_id, &ext);
    if path.is_file() {
        return Ok(path);
    }
    write_atomic(&path, &bytes)?;
    Ok(path)
}

pub fn extension_for_image(bytes: &[u8]) -> Option<&'static str> {
    if bytes.starts_with(b"\x89PNG\r\n\x1a\n") {
        Some(".png")
    } else if bytes.starts_with(b"\xff\xd8\xff") {
        Some(".jpg")
    } else if bytes.starts_with(b"RIFF") && bytes.get(8..12) == Some(b"WEBP") {
        Some(".webp")
    } else {
        None
    }
}

pub fn ensure_parent_dir(path: &PathBuf) -> Result<(), String> {
    ensure_parent(path)
}
