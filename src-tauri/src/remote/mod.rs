mod artwork;
mod cache;
mod catalog;
mod client;
mod discover;
mod progress;
mod tls;

pub use cache::suffix_for_remote_id;
pub use catalog::discover_remote;
pub use progress::{push_playback_to_host, push_reader_to_targets, sync_progress_from_remote};
pub use client::{fetch_remote_library, fetch_remote_stream, pair_with_host};
pub use discover::{discover_nearby_hosts, DiscoveredHost};

use std::path::PathBuf;

use crate::catalog::item::LibraryItem;
use crate::config::KabinConfig;

pub fn ensure_remote_media_file(
    item: &LibraryItem,
    config: &KabinConfig,
    track: u32,
) -> Result<PathBuf, String> {
    let LaunchPlan::RemoteStream {
        host_name,
        remote_id,
        playable,
        size,
        has_artwork: _,
    } = &item.launch
    else {
        return Err("Not a remote stream item".into());
    };
    if !*playable {
        return Err("This item is not playable from the host".into());
    }
    let host = config
        .remote_host_by_name(host_name)
        .ok_or_else(|| format!("Paired host “{host_name}” not found"))?;
    let token = host
        .token
        .clone()
        .filter(|t| !t.is_empty())
        .ok_or_else(|| "Re-pair required".to_string())?;
    let suffix = suffix_for_remote_id(remote_id);
    let host_key = format!("{}:{}:{}", host.address, host.port, host.fingerprint);
    let path = cache::cache_path(&host_key, remote_id, *size, &suffix);
    if path.is_file() {
        return Ok(path);
    }
    let bytes = fetch_remote_stream(&host, &token, remote_id, track)?;
    cache::write_atomic(&path, &bytes)?;
    Ok(path)
}

use crate::catalog::launch::LaunchPlan;
