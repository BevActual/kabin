use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use base64::Engine as _;
use roxmltree::Document;

const PAGE_STYLE: &str = "body{font-family:Georgia,serif;line-height:1.5;margin:1rem;color:#111;background:#fafafa}p{margin:0.6em 0}img{max-width:100%}";

pub fn extract_fb2_pages(path: &Path, title_id: &str) -> Result<Vec<String>, String> {
    let cache = fb2_cache_root(title_id);
    let manifest = cache.join(".kabin-pages.json");
    if manifest.is_file() {
        let raw = fs::read_to_string(&manifest).map_err(|e| e.to_string())?;
        let json: serde_json::Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
        if let Some(arr) = json.get("pages").and_then(|v| v.as_array()) {
            let pages: Vec<String> = arr
                .iter()
                .filter_map(|v| v.as_str().map(str::to_string))
                .collect();
            if !pages.is_empty() {
                return Ok(pages);
            }
        }
    }
    let bytes = fs::read(path).map_err(|e| e.to_string())?;
    let text = String::from_utf8_lossy(&bytes);
    let doc = Document::parse(text.as_ref()).map_err(|e| e.to_string())?;
    fs::create_dir_all(&cache).map_err(|e| e.to_string())?;
    let mut binaries: HashMap<String, String> = HashMap::new(); // id -> data URI
    for node in doc.root().children() {
        if local_name(node.tag_name().name()) != "binary" {
            continue;
        }
        let Some(bid) = node.attribute("id") else {
            continue;
        };
        let Some(text) = node.text() else {
            continue;
        };
        let Ok(data) = base64::engine::general_purpose::STANDARD.decode(text.trim()) else {
            continue;
        };
        let content_type = node.attribute("content-type").unwrap_or("");
        let ext = if content_type.contains("png") {
            ".png"
        } else {
            ".jpg"
        };
        let filename = if bid.contains('.') {
            bid.to_string()
        } else {
            format!("{bid}{ext}")
        };
        let mime = if filename.ends_with(".png") {
            "image/png"
        } else {
            "image/jpeg"
        };
        let encoded = base64::engine::general_purpose::STANDARD.encode(&data);
        binaries.insert(
            bid.to_string(),
            format!("data:{mime};base64,{encoded}"),
        );
    }
    let mut sections = Vec::new();
    for node in doc.root().children() {
        if local_name(node.tag_name().name()) != "body" {
            continue;
        }
        if node.attribute("name").is_some() {
            continue;
        }
        for child in node.children() {
            if local_name(child.tag_name().name()) == "section" {
                sections.push(child);
            }
        }
    }
    if sections.is_empty() {
        return Err("FB2 has no readable sections".into());
    }
    let mut pages = Vec::new();
    for section in sections {
        let body_html = section_html(section, &binaries);
        pages.push(format!(
            "<html><head><meta charset=\"utf-8\"><style>{PAGE_STYLE}</style></head><body>{body_html}</body></html>"
        ));
    }
    fs::write(
        &manifest,
        serde_json::json!({ "pages": pages }).to_string(),
    )
    .map_err(|e| e.to_string())?;
    Ok(pages)
}

fn fb2_cache_root(title_id: &str) -> PathBuf {
    let safe: String = title_id
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() { c } else { '_' })
        .collect();
    dirs::cache_dir()
        .unwrap_or_else(|| PathBuf::from(".cache"))
        .join("kabin")
        .join("fb2")
        .join(safe)
}

fn local_name(tag: &str) -> &str {
    tag.rsplit(':').next().unwrap_or(tag)
}

fn escape_html(text: &str) -> String {
    text.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

fn section_html(node: roxmltree::Node<'_, '_>, binaries: &HashMap<String, String>) -> String {
    let mut out = String::new();
    for child in node.children() {
        match local_name(child.tag_name().name()) {
            "p" | "subtitle" | "text-author" => {
                let text = node_text(child);
                if !text.is_empty() {
                    out.push_str(&format!("<p>{}</p>", escape_html(&text)));
                }
            }
            "image" => {
                if let Some(href) = child
                    .attribute("l:href")
                    .or_else(|| child.attribute("href"))
                {
                    let id = href.trim_start_matches('#');
                    if let Some(uri) = binaries.get(id) {
                        out.push_str(&format!("<p><img src=\"{uri}\" alt=\"\" /></p>"));
                    }
                }
            }
            "section" => out.push_str(&section_html(child, binaries)),
            _ => {}
        }
    }
    out
}

fn node_text(node: roxmltree::Node<'_, '_>) -> String {
    let mut parts = Vec::new();
    for child in node.descendants() {
        if child.is_text() {
            if let Some(t) = child.text() {
                let trimmed = t.trim();
                if !trimmed.is_empty() {
                    parts.push(trimmed);
                }
            }
        }
    }
    parts.join(" ")
}
