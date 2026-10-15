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
        let series = item.series.trim();
        let heading = if series.is_empty() {
            "More in this series".into()
        } else {
            format!("More in {series}")
        };
        return RelatedShelf {
            heading,
            titles: map_titles(&siblings, config),
        };
    }

    let others: Vec<&LibraryItem> = items.iter().filter(|other| other.id != item.id).collect();

    if let Some(lead) = item.creators.first().map(|s| s.trim()).filter(|s| !s.is_empty()) {
        let lead_fold = lead.to_lowercase();
        let same: Vec<_> = others
            .iter()
            .filter(|g| {
                g.creators
                    .iter()
                    .any(|c| c.trim().eq_ignore_ascii_case(&lead_fold))
            })
            .take(LIMIT)
            .copied()
            .collect();
        if !same.is_empty() {
            return RelatedShelf {
                heading: format!("More by {lead}"),
                titles: map_titles(&same, config),
            };
        }
    }

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
    let needle = item.series.trim();
    if needle.is_empty() {
        return Vec::new();
    }
    let needle_fold = needle.to_lowercase();
    let mut matches: Vec<_> = items
        .iter()
        .filter(|other| {
            other.id != item.id
                && other.series.trim().to_lowercase() == needle_fold
        })
        .collect();
    matches.sort_by(|a, b| {
        let ia = a.series_index.unwrap_or(f64::MAX);
        let ib = b.series_index.unwrap_or(f64::MAX);
        ia.partial_cmp(&ib)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.title.to_lowercase().cmp(&b.title.to_lowercase()))
    });
    matches.into_iter().take(limit).collect()
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
