use regex::Regex;
use std::path::Path;

#[derive(Debug, Clone, Default)]
pub struct ParsedName {
    pub title: String,
    pub creators: Vec<String>,
    pub series: String,
    pub series_index: Option<f64>,
}

pub fn parse_media_name(name: &str, media_type: &str) -> ParsedName {
    let raw = Path::new(name)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or(name);
    let text = tidy(raw);
    if text.is_empty() {
        return ParsedName {
            title: raw.to_string(),
            ..Default::default()
        };
    }

    let mut creators = Vec::new();
    let mut series = String::new();
    let mut series_index = None;
    let mut title = text.clone();

    if text.contains(" -- ") {
        let parts: Vec<_> = text.split(" -- ").map(str::trim).filter(|p| !p.is_empty()).collect();
        if let Some(head) = parts.first() {
            title = tidy(head);
        }
        let mut leftovers = Vec::new();
        for part in parts.iter().skip(1) {
            if is_junk(part) {
                continue;
            }
            if !creators.is_empty() {
                leftovers.push(tidy(part));
            } else {
                creators.push(pretty_creator(part));
            }
        }
        if series.is_empty() {
            if let Some(first) = leftovers.first() {
                series = first.clone();
            }
        }
    } else if media_type == "music" && text.contains(" - ") {
        if let Some((artist, album)) = text.split_once(" - ") {
            if !artist.trim().is_empty() && !album.trim().is_empty() {
                title = tidy(album);
                creators.push(pretty_creator(artist));
            }
        }
    }

    if let Some(caps) = volume_re().captures(&title) {
        series = tidy(caps.name("series").map(|m| m.as_str()).unwrap_or(""));
        if let Some(idx) = caps.name("index").and_then(|m| m.as_str().parse().ok()) {
            series_index = Some(idx);
        }
        let rest = tidy(caps.name("rest").map(|m| m.as_str()).unwrap_or(""));
        title = if rest.is_empty() {
            format!("{} {}", series, series_index.unwrap_or(1.0) as i64)
        } else {
            rest
        };
    }

    ParsedName {
        title: restore_leading_article(&title),
        creators: creators.into_iter().filter(|c| !c.is_empty()).collect(),
        series,
        series_index,
    }
}

fn tidy(text: &str) -> String {
    let tag = Regex::new(r"\s*[\[(][^\])]*[\])]\s*").unwrap();
    let mut s = text.replace('_', " ");
    s = tag.replace_all(&s, " ").into_owned();
    s.split_whitespace().collect::<Vec<_>>().join(" ");
    s.trim_matches(|c| c == ' ' || c == '-' || c == '–' || c == ',').trim().to_string()
}

fn is_junk(part: &str) -> bool {
    let token = part.trim();
    if token.is_empty() {
        return true;
    }
    if Regex::new(r"^(?:19|20)\d{2}$").unwrap().is_match(token) {
        return true;
    }
    if token.to_lowercase().starts_with("isbn") {
        return true;
    }
    if Regex::new(r"anna.?s archive|libgen|z-library|zlib").unwrap().is_match(token) {
        return true;
    }
    false
}

fn pretty_creator(name: &str) -> String {
    let re_by = Regex::new(r"((?i)^by\s+)").unwrap();
    restore_leading_article(&re_by.replace(&tidy(name), "").trim().to_string())
}

fn restore_leading_article(name: &str) -> String {
    let re = Regex::new(r"^(?P<body>.+),\s+(?P<article>The|A|An)$").unwrap();
    if let Some(caps) = re.captures(name.trim()) {
        let article = caps.name("article").map(|m| m.as_str()).unwrap_or("");
        let body = caps.name("body").map(|m| m.as_str()).unwrap_or("");
        let art = if article.eq_ignore_ascii_case("the") {
            "The"
        } else {
            article
        };
        return format!("{art} {body}");
    }
    name.to_string()
}

fn volume_re() -> Regex {
    Regex::new(r"(?i)(?P<series>.+?)[,_ ]+(?:vol\.?|volume)\s*(?P<index>\d+)\b(?P<rest>.*)$").unwrap()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_author_title_separator() {
        let parsed = parse_media_name("Dune -- Frank Herbert", "book");
        assert_eq!(parsed.title, "Dune");
        assert_eq!(parsed.creators, vec!["Frank Herbert"]);
    }

    #[test]
    fn parses_volume_series() {
        let parsed = parse_media_name("Saga, Vol. 2 - Chapter One.cbz", "comic");
        assert!(parsed.series.to_lowercase().contains("saga"));
        assert_eq!(parsed.series_index, Some(2.0));
    }
}
