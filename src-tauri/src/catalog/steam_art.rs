use std::fs;
use std::io::Read;
use std::path::PathBuf;

use super::launch::LaunchPlan;

const URLS: [&str; 2] = [
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_600x900.jpg",
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg",
];

fn cache_dir() -> PathBuf {
    dirs::cache_dir()
        .unwrap_or_else(|| PathBuf::from(".cache"))
        .join("kabin")
        .join("steam")
        .join("cover")
}

fn supported_image(data: &[u8]) -> bool {
    data.starts_with(b"\x89PNG\r\n\x1a\n")
        || data.starts_with(b"\xff\xd8\xff")
        || (data.starts_with(b"RIFF") && data.get(8..12) == Some(b"WEBP"))
}

pub fn fetch_steam_cover(appid: &str) -> Option<PathBuf> {
    let dest = cache_dir().join(format!("{appid}.jpg"));
    if dest.is_file() {
        return Some(dest);
    }
    fs::create_dir_all(cache_dir()).ok()?;
    for template in URLS {
        let url = template.replace("{appid}", appid);
        let Ok(response) = ureq::get(&url)
            .set("User-Agent", "kabin/0.1")
            .timeout(std::time::Duration::from_secs(8))
            .call()
        else {
            continue;
        };
        let mut data = Vec::new();
        if response.into_reader().read_to_end(&mut data).is_err() {
            continue;
        }
        if data.is_empty() || data.len() > 15 * 1024 * 1024 || !supported_image(&data) {
            continue;
        }
        let tmp = dest.with_extension("tmp");
        if fs::write(&tmp, &data).is_ok() && fs::rename(&tmp, &dest).is_ok() {
            return Some(dest);
        }
    }
    None
}

pub fn enrich_steam_covers(items: &mut [crate::catalog::item::LibraryItem]) {
    for item in items.iter_mut() {
        if item.source != "steam" {
            continue;
        }
        if item.cover_path.is_some() {
            continue;
        }
        let LaunchPlan::Steam { appid } = &item.launch else {
            continue;
        };
        if let Some(path) = fetch_steam_cover(appid) {
            item.cover_path = Some(path.to_string_lossy().into_owned());
        }
    }
}
