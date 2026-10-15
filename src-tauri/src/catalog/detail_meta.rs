use std::path::Path;

use super::item::LibraryItem;
use super::launch::LaunchPlan;

pub fn format_size(size: u64) -> String {
    if size < 1024 {
        return format!("{size} B");
    }
    let mut value = size as f64;
    let mut unit = "KB";
    value /= 1024.0;
    if value >= 1024.0 {
        value /= 1024.0;
        unit = "MB";
    }
    if value >= 1024.0 {
        value /= 1024.0;
        unit = "GB";
    }
    if unit == "KB" {
        return format!("{:.0} {unit}", value);
    }
    let text = format!("{value:.1}");
    format!("{} {unit}", text.trim_end_matches(".0"))
}

fn file_meta(path: &Path) -> Vec<String> {
    let Ok(meta) = path.metadata() else {
        return Vec::new();
    };
    if !meta.is_file() {
        return Vec::new();
    }
    let mut lines = Vec::new();
    if let Some(ext) = path.extension().and_then(|e| e.to_str()) {
        lines.push(ext.to_uppercase());
    }
    lines.push(format_size(meta.len()));
    lines
}

pub fn detail_lines(item: &LibraryItem) -> Vec<String> {
    match &item.launch {
        LaunchPlan::OpenPath { path } => file_meta(path),
        LaunchPlan::Command { argv, .. } => argv
            .last()
            .map(|p| file_meta(Path::new(p)))
            .unwrap_or_default(),
        LaunchPlan::Steam { appid } => vec![format!("Steam · {appid}")],
        LaunchPlan::Desktop { desktop_file } => vec![desktop_file
            .file_name()
            .map(|n| n.to_string_lossy().into_owned())
            .unwrap_or_else(|| "Desktop app".into())],
        LaunchPlan::RemoteGame { host_name, .. } => vec![format!("Remote · {host_name}")],
        LaunchPlan::RemoteStream { host_name, size, .. } => {
            let mut lines = vec![format!("Remote · {host_name}")];
            if *size > 0 {
                lines.push(format_size(*size));
            }
            lines
        }
    }
}
