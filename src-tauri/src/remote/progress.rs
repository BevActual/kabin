use serde_json::Value;

use super::client::push_remote_progress;
use crate::catalog::item::LibraryItem;
use crate::catalog::launch::LaunchPlan;
use crate::config::{KabinConfig, RemoteHostEntry};

pub fn push_playback_to_host(
    config: &KabinConfig,
    item: &LibraryItem,
    position: f64,
    duration: f64,
    track: u32,
) {
    if item.source != "remote" {
        return;
    }
    let Some((host, remote_id)) = remote_host_ref(config, item) else {
        return;
    };
    let token = host.token.as_deref().unwrap_or("");
    let _ = push_remote_progress(
        &host,
        token,
        &remote_id,
        position,
        duration,
        track,
        None,
    );
}

pub fn push_reader_to_targets(
    config: &KabinConfig,
    items: &[LibraryItem],
    item: &LibraryItem,
    page: u32,
    total: u32,
    scroll: Option<f64>,
) {
    for (host, remote_id) in reader_progress_targets(config, items, item) {
        let Some(token) = host.token.as_deref() else {
            continue;
        };
        let _ = push_remote_progress(
            &host,
            token,
            &remote_id,
            page as f64,
            total as f64,
            0,
            scroll,
        );
    }
}

pub fn sync_progress_from_remote(items: &[LibraryItem], config: &mut KabinConfig) -> bool {
    let mut local_sizes: std::collections::HashMap<String, u64> = std::collections::HashMap::new();
    for item in items {
        if item.source == "remote" {
            continue;
        }
        if !matches!(item.kind_id.as_str(), "book" | "comic" | "pdf") {
            continue;
        }
        if let Some(size) = local_file_size(item) {
            local_sizes.insert(item.id.clone(), size);
        }
    }
    let mut adopted = false;
    for item in items {
        if item.source != "remote" || !matches!(item.kind_id.as_str(), "book" | "comic" | "pdf") {
            continue;
        }
        let LaunchPlan::RemoteStream { remote_id, size, .. } = &item.launch else {
            continue;
        };
        if *size == 0 || local_sizes.get(remote_id.as_str()) != Some(size) {
            continue;
        }
        let Some(progress) = item.host_progress.as_ref() else {
            continue;
        };
        if config.adopt_progress(remote_id, progress, false) {
            adopted = true;
        }
    }
    adopted
}

fn local_file_size(item: &LibraryItem) -> Option<u64> {
    if let LaunchPlan::OpenPath { path } = &item.launch {
        return path.metadata().ok().map(|m| m.len());
    }
    None
}

fn remote_host_ref(config: &KabinConfig, item: &LibraryItem) -> Option<(RemoteHostEntry, String)> {
    let (host_name, remote_id) = match &item.launch {
        LaunchPlan::RemoteStream { host_name, remote_id, .. } => {
            (host_name.clone(), remote_id.clone())
        }
        LaunchPlan::RemoteGame { host_name, remote_id, .. } => {
            (host_name.clone(), remote_id.clone())
        }
        _ => return None,
    };
    let host = config.remote_host_by_name(&host_name)?;
    let token = host.token.clone().filter(|t| !t.is_empty())?;
    Some((
        RemoteHostEntry {
            token: Some(token),
            ..host
        },
        remote_id,
    ))
}

pub fn reader_progress_targets(
    config: &KabinConfig,
    items: &[LibraryItem],
    item: &LibraryItem,
) -> Vec<(RemoteHostEntry, String)> {
    if item.source == "remote" {
        return remote_host_ref(config, item)
            .map(|(host, id)| vec![(host, id)])
            .unwrap_or_default();
    }
    let mut out = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for remote in items.iter().filter(|i| i.source == "remote") {
        let LaunchPlan::RemoteStream { remote_id, host_name, .. } = &remote.launch else {
            continue;
        };
        if remote_id != &item.id {
            continue;
        }
        let Some(host) = config.remote_host_by_name(host_name) else {
            continue;
        };
        let Some(token) = host.token.clone().filter(|t| !t.is_empty()) else {
            continue;
        };
        let key = (host.address.clone(), host.port, token.clone());
        if !seen.insert(key) {
            continue;
        }
        out.push((
            RemoteHostEntry {
                token: Some(token),
                ..host
            },
            item.id.clone(),
        ));
    }
    out
}

pub fn progress_value(
    position: f64,
    duration: f64,
    track: u32,
    scroll: Option<f64>,
) -> Value {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0);
    let mut payload = serde_json::json!({
        "position": position.max(0.0),
        "duration": duration.max(0.0),
        "track": track,
        "updated_at": now,
    });
    if let Some(scroll) = scroll {
        if let Some(obj) = payload.as_object_mut() {
            obj.insert("scroll".into(), serde_json::json!(scroll.clamp(0.0, 1.0)));
        }
    }
    payload
}
