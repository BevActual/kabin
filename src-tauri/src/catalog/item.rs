use super::kinds::{self, MediaKind};
use super::launch::LaunchPlan;
use serde::Serialize;
use serde_json::Value;

#[derive(Debug, Clone)]
pub struct LibraryItem {
    pub id: String,
    pub title: String,
    pub subtitle: String,
    pub kind_id: String,
    pub source: String,
    pub cover_path: Option<String>,
    pub added_at: f64,
    pub track_count: u32,
    pub launch: LaunchPlan,
    pub host_progress: Option<Value>,
}

impl LibraryItem {
    pub fn sort_key(&self) -> String {
        self.title.to_lowercase()
    }

    pub fn aspect(&self) -> &'static str {
        kinds::kind_by_id(&self.kind_id).aspect
    }

    pub fn can_launch(&self) -> bool {
        match &self.launch {
            LaunchPlan::RemoteGame { .. } => false,
            LaunchPlan::RemoteStream { playable, .. } => {
                *playable && self.supports_in_app_playback()
            }
            _ => true,
        }
    }

    pub fn supports_in_app_playback(&self) -> bool {
        matches!(
            self.kind_id.as_str(),
            "music" | "video" | "tv" | "book" | "comic"
        )
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CatalogTitle {
    pub id: String,
    pub title: String,
    pub subtitle: String,
    pub kind: String,
    pub aspect: String,
    pub progress: Option<f32>,
    pub accent_hue: u16,
    pub cover_path: Option<String>,
    pub can_launch: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub play_count: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub play_time_label: Option<String>,
}

impl CatalogTitle {
    pub fn from_item(item: &LibraryItem, progress: Option<f32>, subtitle: Option<String>) -> Self {
        Self::from_item_with_config(item, progress, subtitle, None)
    }

    pub fn from_item_with_config(
        item: &LibraryItem,
        progress: Option<f32>,
        subtitle: Option<String>,
        config: Option<&crate::config::KabinConfig>,
    ) -> Self {
        let (play_count, play_time_label) = if item.kind_id == "game" {
            config.map(|cfg| {
                let count = cfg.play_count(&item.id);
                let label = crate::sessions::format_play_time(cfg.play_seconds(&item.id) as f64);
                (
                    if count > 0 { Some(count) } else { None },
                    if label.is_empty() { None } else { Some(label) },
                )
            }).unwrap_or((None, None))
        } else {
            (None, None)
        };
        Self {
            id: item.id.clone(),
            title: item.title.clone(),
            subtitle: subtitle.unwrap_or_else(|| item.subtitle.clone()),
            kind: item.kind_id.clone(),
            aspect: item.aspect().to_string(),
            progress,
            accent_hue: kinds::accent_hue(&item.kind_id),
            cover_path: item.cover_path.clone(),
            can_launch: item.can_launch(),
            play_count,
            play_time_label,
        }
    }

    pub fn progress_for_item(
        item: &LibraryItem,
        config: &crate::config::KabinConfig,
    ) -> Option<f32> {
        if let Some(ratio) = config.progress_ratio(&item.id, item.track_count) {
            return Some(ratio);
        }
        remote_progress_ratio(item)
    }
}

pub fn remote_progress_ratio(item: &LibraryItem) -> Option<f32> {
    let progress = item.host_progress.as_ref()?;
    let position = progress.get("position")?.as_f64()? as f32;
    let duration = progress.get("duration")?.as_f64()? as f32;
    let track = progress
        .get("track")
        .and_then(|v| v.as_u64())
        .unwrap_or(0) as u32;
    let total = item.track_count.max(1);
    if total > 1 {
        let frac = if duration > 0.0 {
            position / duration
        } else {
            0.0
        };
        let ratio = (track as f32 + frac.clamp(0.0, 1.0)) / total as f32;
        return if ratio > 0.0 { Some(ratio.min(1.0)) } else { None };
    }
    if duration <= 0.0 || position <= 0.0 {
        return None;
    }
    Some((position / duration).min(1.0))
}

pub fn kind_label(kind: &MediaKind) -> String {
    kind.plural.to_string()
}
