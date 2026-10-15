use super::item::{CatalogTitle, LibraryItem};
use crate::config::KabinConfig;

pub fn search_blob(item: &LibraryItem) -> String {
    let mut parts = vec![
        item.title.clone(),
        item.subtitle.clone(),
        item.source.clone(),
        item.series.clone(),
        item.kind_id.clone(),
        item.id.clone(),
    ];
    parts.extend(item.creators.clone());
    parts.join(" ").to_lowercase()
}

pub fn matches_query(item: &LibraryItem, query: &str) -> bool {
    let needle = query.trim().to_lowercase();
    if needle.is_empty() {
        return true;
    }
    search_blob(item).contains(&needle)
}

pub fn search_titles(
    items: &[LibraryItem],
    config: &KabinConfig,
    query: &str,
    limit: usize,
) -> Vec<CatalogTitle> {
    let needle = query.trim();
    if needle.is_empty() {
        return Vec::new();
    }
    let mut hits: Vec<_> = items
        .iter()
        .filter(|item| matches_query(item, needle))
        .collect();
    hits.sort_by_key(|item| item.sort_key());
    hits.into_iter()
        .take(limit)
        .map(|item| {
            CatalogTitle::from_item_with_config(
                item,
                CatalogTitle::progress_for_item(item, config),
                None,
                Some(config),
            )
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::catalog::launch::LaunchPlan;

    fn sample_item(title: &str, creator: &str) -> LibraryItem {
        LibraryItem {
            id: format!("book:{title}"),
            title: title.into(),
            subtitle: "Books".into(),
            kind_id: "book".into(),
            source: "book".into(),
            cover_path: None,
            added_at: 0.0,
            track_count: 1,
            launch: LaunchPlan::OpenPath {
                path: std::path::PathBuf::from("/tmp/x"),
            },
            host_progress: None,
            series: String::new(),
            series_index: None,
            creators: vec![creator.into()],
        }
    }

    #[test]
    fn finds_by_creator() {
        let item = sample_item("Dune", "Frank Herbert");
        assert!(matches_query(&item, "herbert"));
        assert!(!matches_query(&item, "asimov"));
    }
}
