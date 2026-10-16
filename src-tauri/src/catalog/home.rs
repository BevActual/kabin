use std::collections::{HashMap, HashSet};

use super::item::{CatalogTitle, LibraryItem};
use super::kinds::{self, FOLDER_KINDS};
use crate::config::KabinConfig;

const SHELF_LIMIT: usize = 8;
const ADDED_MIN_LIBRARY: usize = 5;

pub struct HomeShelf {
    pub id: String,
    pub label: String,
    pub titles: Vec<CatalogTitle>,
}

fn kind_order(items: &[LibraryItem], recent_ids: &[String]) -> Vec<String> {
    let by_id: HashMap<_, _> = items.iter().map(|item| (item.id.as_str(), item)).collect();
    let mut order = Vec::new();
    let mut seen = HashSet::new();
    for id in recent_ids {
        if let Some(item) = by_id.get(id.as_str()) {
            if seen.insert(item.kind_id.clone()) {
                order.push(item.kind_id.clone());
            }
        }
    }
    for kind_id in ["game", "book", "comic", "music", "video", "tv"] {
        if seen.insert(kind_id.to_string()) {
            order.push(kind_id.to_string());
        }
    }
    order
}

fn continue_subtitle(config: &KabinConfig, item: &LibraryItem) -> String {
    if let Some(ratio) = config.progress_ratio(&item.id, item.track_count) {
        if ratio > 0.0 {
            return format!("Resume · {}%", (ratio * 100.0).round() as u32);
        }
    }
    item.subtitle.clone()
}

pub fn build_home_shelves(config: &KabinConfig, items: &[LibraryItem]) -> Vec<HomeShelf> {
    let recent_ids = config.recent_ordered();
    let by_id: HashMap<_, _> = items.iter().map(|item| (item.id.clone(), item)).collect();
    let mut shelves = Vec::new();

    let favorite_ids: HashSet<_> = config.favorite_ids().into_iter().collect();
    if !favorite_ids.is_empty() {
        let mut favorites: Vec<_> = items
            .iter()
            .filter(|item| favorite_ids.contains(&item.id))
            .collect();
        favorites.sort_by_key(|item| item.sort_key());
        let titles: Vec<CatalogTitle> = favorites
            .into_iter()
            .take(SHELF_LIMIT)
            .map(|item| {
                CatalogTitle::from_item_with_config(
                    item,
                    CatalogTitle::progress_for_item(item, config),
                    None,
                    Some(config),
                )
            })
            .collect();
        if !titles.is_empty() {
            shelves.push(HomeShelf {
                id: "favorites".into(),
                label: "Favorites".into(),
                titles,
            });
        }
    }

    let mut continue_ids = HashSet::new();

    for kind_id in kind_order(items, &recent_ids) {
        let kind = kinds::kind_by_id(&kind_id);
        let mut row = Vec::new();
        for id in &recent_ids {
            let Some(item) = by_id.get(id) else { continue };
            if item.kind_id != kind_id {
                continue;
            }
            let progress = config.progress_ratio(&item.id, item.track_count);
            row.push(CatalogTitle::from_item_with_config(
                item,
                progress.filter(|p| *p > 0.0),
                Some(continue_subtitle(config, item)),
                Some(config),
            ));
            if row.len() >= SHELF_LIMIT {
                break;
            }
        }
        if !row.is_empty() {
            continue_ids.extend(row.iter().map(|t| t.id.clone()));
            shelves.push(HomeShelf {
                id: format!("continue-{kind_id}"),
                label: format!("Continue · {}", kind.plural),
                titles: row,
            });
        }
    }

    for kind in FOLDER_KINDS {
        let kind_total = items.iter().filter(|i| i.kind_id == kind.id).count();
        if kind_total < ADDED_MIN_LIBRARY {
            continue;
        }
        let mut added: Vec<_> = items
            .iter()
            .filter(|i| i.kind_id == kind.id && i.added_at > 0.0)
            .collect();
        added.sort_by(|a, b| b.added_at.partial_cmp(&a.added_at).unwrap_or(std::cmp::Ordering::Equal));
        let titles: Vec<CatalogTitle> = added
            .into_iter()
            .filter(|i| !continue_ids.contains(&i.id))
            .take(SHELF_LIMIT)
            .map(|item| CatalogTitle::from_item_with_config(item, None, None, Some(config)))
            .collect();
        if !titles.is_empty() {
            shelves.push(HomeShelf {
                id: format!("added-{}", kind.id),
                label: format!("Recently added · {}", kind.plural),
                titles,
            });
        }
    }

    shelves
}
