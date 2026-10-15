use super::item::{CatalogTitle, LibraryItem};
use crate::config::KabinConfig;

pub struct RelatedShelf {
    pub heading: String,
    pub titles: Vec<CatalogTitle>,
}

pub fn related_shelf(item: &LibraryItem, items: &[LibraryItem], config: &KabinConfig) -> RelatedShelf {
    const LIMIT: usize = 12;
    let siblings = related_by_series(item, items, LIMIT);
    if !siblings.is_empty() {
        let series = item.subtitle.trim();
        let heading = if series.is_empty() {
            "More in this series".into()
        } else {
            format!("More in {series}")
        };
        return RelatedShelf {
            heading,
            titles: siblings
                .into_iter()
                .map(|i| CatalogTitle::from_item_with_config(i, CatalogTitle::progress_for_item(i, config), None, Some(config)))
                .collect(),
        };
    }

    let others: Vec<&LibraryItem> = items
        .iter()
        .filter(|other| other.id != item.id)
        .collect();

    if item.source == "roms" && !item.subtitle.is_empty() {
        let same: Vec<_> = others
            .iter()
            .filter(|g| g.source == "roms" && g.subtitle == item.subtitle)
            .take(LIMIT)
            .copied()
            .collect();
        if !same.is_empty() {
            return RelatedShelf {
                heading: format!("More from {}", item.subtitle),
                titles: map_titles(&same, config),
            };
        }
    }

    if item.source == "remote" && !item.subtitle.is_empty() {
        let same: Vec<_> = others
            .iter()
            .filter(|g| {
                g.source == "remote" && g.subtitle == item.subtitle && g.kind_id == item.kind_id
            })
            .take(LIMIT)
            .copied()
            .collect();
        if !same.is_empty() {
            return RelatedShelf {
                heading: format!("More on {}", item.subtitle),
                titles: map_titles(&same, config),
            };
        }
    }

    if item.source == "steam" && item.kind_id == "game" {
        let same: Vec<_> = others
            .iter()
            .filter(|g| g.source == "steam" && g.kind_id == "game")
            .take(LIMIT)
            .copied()
            .collect();
        if !same.is_empty() {
            return RelatedShelf {
                heading: "More on Steam".into(),
                titles: map_titles(&same, config),
            };
        }
    }

    let same_kind: Vec<_> = others
        .iter()
        .filter(|g| g.kind_id == item.kind_id)
        .take(LIMIT)
        .copied()
        .collect();
    if !same_kind.is_empty() {
        let label = kind_label(&item.kind_id);
        return RelatedShelf {
            heading: format!("More {label}"),
            titles: map_titles(&same_kind, config),
        };
    }

    RelatedShelf {
        heading: String::new(),
        titles: Vec::new(),
    }
}

fn map_titles(items: &[&LibraryItem], config: &KabinConfig) -> Vec<CatalogTitle> {
    items
        .iter()
        .map(|i| {
            CatalogTitle::from_item_with_config(
                i,
                CatalogTitle::progress_for_item(i, config),
                None,
                Some(config),
            )
        })
        .collect()
}

fn related_by_series<'a>(
    item: &LibraryItem,
    items: &'a [LibraryItem],
    limit: usize,
) -> Vec<&'a LibraryItem> {
    let needle = series_key(&item.title);
    if needle.is_empty() {
        return Vec::new();
    }
    let mut matches: Vec<_> = items
        .iter()
        .filter(|other| other.id != item.id && series_key(&other.title) == needle)
        .collect();
    matches.sort_by_key(|g| g.title.to_lowercase());
    matches.into_iter().take(limit).collect()
}

fn series_key(title: &str) -> String {
    let base = title.split(':').next().unwrap_or(title).trim();
    if base.is_empty() {
        return String::new();
    }
    base.to_lowercase()
}

fn kind_label(kind_id: &str) -> &'static str {
    match kind_id {
        "game" => "games",
        "music" => "music",
        "video" => "movies",
        "tv" => "TV",
        "book" => "books",
        "comic" => "comics",
        _ => "titles",
    }
}
