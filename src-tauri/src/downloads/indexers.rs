use std::io::Read;

use super::import::format_bytes;
use super::settings::Indexer;

#[derive(Debug, Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ReleaseHit {
    pub title: String,
    pub size_bytes: u64,
    pub size_label: String,
    pub link: String,
    pub protocol: String,
    pub indexer: String,
    pub seeders: Option<u32>,
}

pub fn search_indexers(
    indexers: &[Indexer],
    query: &str,
    quality: &str,
) -> Result<Vec<ReleaseHit>, String> {
    if indexers.is_empty() {
        return Err("Add an indexer in Settings".into());
    }
    let query = query.trim();
    if query.is_empty() {
        return Err("Enter a title to search".into());
    }
    let mut hits = Vec::new();
    let mut errors = Vec::new();
    for indexer in indexers {
        match fetch_indexer(indexer, query) {
            Ok(mut found) => hits.append(&mut found),
            Err(error) => errors.push(format!("{}: {error}", indexer.name)),
        }
    }
    if hits.is_empty() && !errors.is_empty() {
        return Err(errors.join(" "));
    }
    hits.retain(|hit| matches_quality(&hit.title, quality));
    hits.sort_by(|left, right| right.seeders.unwrap_or(0).cmp(&left.seeders.unwrap_or(0)));
    hits.truncate(40);
    Ok(hits)
}

fn fetch_indexer(indexer: &Indexer, query: &str) -> Result<Vec<ReleaseHit>, String> {
    let url = search_url(indexer, query)?;
    let response = ureq::get(&url)
        .timeout(std::time::Duration::from_secs(25))
        .set("User-Agent", "Kabin")
        .call()
        .map_err(|error| redact(&error.to_string(), &indexer.api_key))?;
    let mut body = Vec::new();
    response
        .into_reader()
        .take(5_000_000)
        .read_to_end(&mut body)
        .map_err(|error| error.to_string())?;
    let xml = String::from_utf8_lossy(&body);
    let protocol = if indexer.kind == "newznab" {
        "usenet"
    } else {
        "torrent"
    };
    parse_feed(&xml, &indexer.name, protocol).map_err(|error| redact(&error, &indexer.api_key))
}

pub fn search_url(indexer: &Indexer, query: &str) -> Result<String, String> {
    let base = indexer.url.trim().trim_end_matches('/');
    if !(base.starts_with("http://") || base.starts_with("https://")) {
        return Err("Indexer address must start with http:// or https://".into());
    }
    let separator = if base.contains('?') { '&' } else { '?' };
    Ok(format!(
        "{base}{separator}t=search&q={}&apikey={}",
        urlencode(query),
        urlencode(&indexer.api_key)
    ))
}

pub fn parse_feed(xml: &str, indexer: &str, protocol: &str) -> Result<Vec<ReleaseHit>, String> {
    let doc = roxmltree::Document::parse(xml).map_err(|e| format!("Indexer returned {e}"))?;
    if let Some(error) = doc.descendants().find(|node| local_name(node) == "error") {
        let description = error
            .attribute("description")
            .unwrap_or("Indexer rejected the search");
        return Err(description.to_string());
    }
    let mut hits = Vec::new();
    for item in doc.descendants().filter(|node| local_name(node) == "item") {
        let title = child_text(&item, "title");
        if title.is_empty() {
            continue;
        }
        let link = enclosure_url(&item)
            .or_else(|| nonempty(child_text(&item, "link")))
            .or_else(|| nonempty(child_text(&item, "guid")))
            .unwrap_or_default();
        if link.is_empty() {
            continue;
        }
        let size_bytes = child_text(&item, "size")
            .parse()
            .ok()
            .or_else(|| enclosure_length(&item))
            .unwrap_or(0);
        let seeders = item.descendants().find_map(|node| {
            if local_name(&node) != "attr" {
                return None;
            }
            let name = node.attribute("name")?;
            if name != "seeders" && name != "seeds" {
                return None;
            }
            node.attribute("value")?.parse().ok()
        });
        let protocol = if link.to_ascii_lowercase().starts_with("magnet:") {
            "torrent"
        } else {
            protocol
        };
        hits.push(ReleaseHit {
            title,
            size_label: format_bytes(size_bytes),
            size_bytes,
            link,
            protocol: protocol.to_string(),
            indexer: indexer.to_string(),
            seeders,
        });
    }
    Ok(hits)
}

pub fn matches_quality(title: &str, quality: &str) -> bool {
    let Some(found) = detected_quality(title) else {
        return true;
    };
    let minimum = match quality {
        "2160p" => 2160,
        "1080p" => 1080,
        "720p" => 720,
        _ => 0,
    };
    found >= minimum
}

fn detected_quality(title: &str) -> Option<u16> {
    let title = title.to_ascii_lowercase();
    if title.contains("2160p") || title.contains("4k") || title.contains("uhd") {
        Some(2160)
    } else if title.contains("1080p") {
        Some(1080)
    } else if title.contains("720p") {
        Some(720)
    } else {
        None
    }
}

fn local_name<'a>(node: &roxmltree::Node<'a, 'a>) -> &'a str {
    if node.is_element() {
        node.tag_name().name()
    } else {
        ""
    }
}

fn child_text(item: &roxmltree::Node<'_, '_>, name: &str) -> String {
    item.descendants()
        .find(|node| local_name(node) == name)
        .and_then(|node| node.text())
        .unwrap_or("")
        .trim()
        .to_string()
}

fn enclosure_url(item: &roxmltree::Node<'_, '_>) -> Option<String> {
    item.descendants().find_map(|node| {
        if local_name(&node) == "enclosure" {
            nonempty(node.attribute("url").unwrap_or("").to_string())
        } else {
            None
        }
    })
}

fn enclosure_length(item: &roxmltree::Node<'_, '_>) -> Option<u64> {
    item.descendants().find_map(|node| {
        if local_name(&node) == "enclosure" {
            node.attribute("length")?.parse().ok()
        } else {
            None
        }
    })
}

fn nonempty(value: String) -> Option<String> {
    if value.trim().is_empty() {
        None
    } else {
        Some(value)
    }
}

fn urlencode(value: &str) -> String {
    let mut out = String::new();
    for byte in value.bytes() {
        match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(byte as char);
            }
            _ => out.push_str(&format!("%{byte:02X}")),
        }
    }
    out
}

fn redact(text: &str, secret: &str) -> String {
    if secret.is_empty() {
        text.to_string()
    } else {
        text.replace(secret, "•••")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_torznab_and_filters_quality() {
        let xml = r#"
            <rss xmlns:torznab="http://torznab.com/schemas/2015/feed"><channel>
              <item>
                <title>Example 720p</title>
                <size>1000</size>
                <enclosure url="magnet:?xt=urn:btih:abc" length="1000" />
                <torznab:attr name="seeders" value="4" />
              </item>
              <item>
                <title>Example 1080p</title>
                <link>magnet:?xt=urn:btih:def</link>
                <torznab:attr name="seeders" value="12" />
              </item>
            </channel></rss>
        "#;
        let hits = parse_feed(xml, "Films", "torrent").unwrap();
        assert_eq!(hits.len(), 2);
        assert_eq!(hits[0].seeders, Some(4));
        assert!(matches_quality("Example 1080p", "1080p"));
        assert!(!matches_quality("Example 720p", "1080p"));
        assert!(matches_quality("Example 2160p UHD", "1080p"));
        assert!(matches_quality("Example", "1080p"));
    }

    #[test]
    fn surfaces_indexer_errors() {
        let xml = r#"<error code="100" description="Incorrect API key" />"#;
        let error = parse_feed(xml, "Films", "torrent").unwrap_err();
        assert!(error.contains("Incorrect API key"));
    }
}
