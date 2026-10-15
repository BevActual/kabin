use std::collections::{HashMap, HashSet};
use std::thread;

use serde_json::Value;

use super::artwork::enrich_remote_artwork;
use super::client::fetch_remote_library;
use crate::catalog::item::LibraryItem;
use crate::catalog::launch::LaunchPlan;
use crate::catalog::kind_by_id;
use crate::config::{KabinConfig, RemoteHostEntry};

#[derive(Debug, Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RemoteHostStatus {
    pub name: String,
    pub state: String,
    pub message: String,
}

pub fn discover_remote(
    config: &KabinConfig,
) -> (Vec<LibraryItem>, HashMap<String, RemoteHostStatus>) {
    let hidden = config.hidden_ids();
    let hosts = config.remote_hosts();
    if hosts.is_empty() {
        return (Vec::new(), HashMap::new());
    }
    let mut handles = Vec::new();
    for host in hosts {
        let host = host.clone();
        let hidden = hidden.clone();
        handles.push(thread::spawn(move || fetch_host_catalog(host, hidden)));
    }
    let mut items = Vec::new();
    let mut statuses = HashMap::new();
    for handle in handles {
        if let Ok((name, status, host_items)) = handle.join() {
            statuses.insert(name.clone(), status);
            items.extend(host_items);
        }
    }
    items.sort_by(|a, b| a.sort_key().cmp(&b.sort_key()));
    (items, statuses)
}

fn fetch_host_catalog(
    host: RemoteHostEntry,
    hidden: HashSet<String>,
) -> (String, RemoteHostStatus, Vec<LibraryItem>) {
    let name = host.name.clone();
    let Some(token) = host.token.clone().filter(|t| !t.is_empty()) else {
        return (
            name.clone(),
            RemoteHostStatus {
                name,
                state: "auth".into(),
                message: "Pairing required".into(),
            },
            Vec::new(),
        );
    };
    match fetch_remote_library(&host, &token) {
        Ok(payload) => {
            let mut items = items_from_payload(&host, &payload, &hidden);
            enrich_remote_artwork(&host, &mut items);
            (
                name.clone(),
                RemoteHostStatus {
                    name,
                    state: "online".into(),
                    message: "Online".into(),
                },
                items,
            )
        }
        Err(err) => {
            let (state, message) = if err.contains("Re-pair") {
                ("auth", "Re-pair required")
            } else if err.contains("fingerprint") {
                ("auth", "Host identity changed")
            } else {
                ("offline", err.as_str())
            };
            (
                name.clone(),
                RemoteHostStatus {
                    name,
                    state: state.into(),
                    message: message.into(),
                },
                Vec::new(),
            )
        }
    }
}

fn items_from_payload(
    host: &RemoteHostEntry,
    payload: &Value,
    hidden: &HashSet<String>,
) -> Vec<LibraryItem> {
    let entries = payload
        .get("items")
        .or_else(|| payload.get("games"))
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let mut items = Vec::new();
    for remote in entries {
        let Some(item) = item_from_remote(host, &remote, hidden) else {
            continue;
        };
        items.push(item);
    }
    items
}

fn reader_supported(remote_id: &str) -> bool {
    let lower = remote_id.to_lowercase();
    [".pdf", ".epub", ".cbz", ".txt", ".fb2", ".cbr", ".cbt", ".cb7"]
        .iter()
        .any(|ext| lower.ends_with(ext))
}

fn item_from_remote(
    host: &RemoteHostEntry,
    remote: &Value,
    hidden: &HashSet<String>,
) -> Option<LibraryItem> {
    let remote_id = remote.get("id")?.as_str()?.trim();
    let title = remote.get("title")?.as_str()?.trim();
    if remote_id.is_empty() || title.is_empty() {
        return None;
    }
    let host_name = host.name.clone();
    let id = format!("remote:{host_name}:{remote_id}");
    if hidden.contains(&id) {
        return None;
    }
    let media_type = remote
        .get("media_type")
        .and_then(|v| v.as_str())
        .unwrap_or("game");
    let kind_id = kind_by_id(media_type).id.to_string();
    let mut playable = remote.get("playable").and_then(|v| v.as_bool()).unwrap_or(false);
    if matches!(kind_id.as_str(), "book" | "comic") {
        playable = playable && reader_supported(remote_id);
    }
    let track_count = remote
        .get("track_count")
        .and_then(|v| v.as_u64())
        .unwrap_or(0) as u32;
    let host_progress = remote.get("progress").cloned();
    let size = remote.get("size").and_then(|v| v.as_u64()).unwrap_or(0);
    let has_artwork = remote
        .get("has_artwork")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let appid = remote
        .get("appid")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let launch = if kind_id == "game" {
        LaunchPlan::RemoteGame {
            host_name: host_name.clone(),
            remote_id: remote_id.to_string(),
            playable,
            has_artwork,
            appid,
        }
    } else {
        LaunchPlan::RemoteStream {
            host_name: host_name.clone(),
            remote_id: remote_id.to_string(),
            playable,
            size,
            has_artwork,
        }
    };
    let series = remote
        .get("series")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let series_index = remote.get("series_index").and_then(|v| v.as_f64());
    let creators: Vec<String> = remote
        .get("creators")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|v| v.as_str().map(str::to_string))
                .collect()
        })
        .unwrap_or_default();
    Some(LibraryItem {
        id,
        title: title.to_string(),
        subtitle: host_name,
        kind_id,
        source: "remote".into(),
        cover_path: None,
        added_at: 0.0,
        track_count: track_count.max(1),
        launch,
        host_progress: host_progress,
        series,
        series_index,
        creators,
    })
}
