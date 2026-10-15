use super::kinds::{self, MediaKind};
use serde::Serialize;

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
}

impl LibraryItem {
    pub fn sort_key(&self) -> String {
        self.title.to_lowercase()
    }

    pub fn aspect(&self) -> &'static str {
        kinds::kind_by_id(&self.kind_id).aspect
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
}

impl CatalogTitle {
    pub fn from_item(item: &LibraryItem, progress: Option<f32>, subtitle: Option<String>) -> Self {
        Self {
            id: item.id.clone(),
            title: item.title.clone(),
            subtitle: subtitle.unwrap_or_else(|| item.subtitle.clone()),
            kind: item.kind_id.clone(),
            aspect: item.aspect().to_string(),
            progress,
            accent_hue: kinds::accent_hue(&item.kind_id),
            cover_path: item.cover_path.clone(),
        }
    }
}

pub fn kind_label(kind: &MediaKind) -> String {
    kind.plural.to_string()
}
