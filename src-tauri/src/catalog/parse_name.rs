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

    if let Some(episode) = parse_episode(&title) {
        series = episode.series;
        series_index = Some(episode.index);
        title = episode.title;
    } else if let Some(caps) = volume_re().captures(&title) {
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

struct EpisodeName {
    series: String,
    index: f64,
    title: String,
}

/// Season and episode packed as `season * 1000 + episode`, so a show sorts
/// in air order. Book volumes stay small numbers and do not use this form.
pub fn episode_label(index: f64) -> Option<String> {
    let value = index.round() as u32;
    let season = value / 1000;
    let episode = value % 1000;
    if value < 1000 || episode == 0 {
        return None;
    }
    Some(format!("S{season} E{episode}"))
}

fn parse_episode(title: &str) -> Option<EpisodeName> {
    let normalized = title.replace('.', " ");
    for pattern in [season_episode_re(), cross_episode_re()] {
        let Some(caps) = pattern.captures(&normalized) else {
            continue;
        };
        let series = tidy(caps.name("series").map(|m| m.as_str()).unwrap_or(""));
        let Some(season) = caps.name("season").and_then(|m| m.as_str().parse::<u32>().ok()) else {
            continue;
        };
        let Some(episode) = caps
            .name("episode")
            .and_then(|m| m.as_str().parse::<u32>().ok())
        else {
            continue;
        };
        if series.is_empty() || episode == 0 || season > 99 {
            continue;
        }
        let rest = tidy(caps.name("rest").map(|m| m.as_str()).unwrap_or(""));
        return Some(EpisodeName {
            series,
            index: (season * 1000 + episode) as f64,
            title: if rest.is_empty() {
                format!("Episode {episode}")
            } else {
                rest
            },
        });
    }
    None
}

fn season_episode_re() -> Regex {
    Regex::new(
        r"(?i)^(?P<series>.+?)\s+[s](?P<season>\d{1,2})\s*[e](?P<episode>\d{1,3})\b[\s\-_]*(?P<rest>.*)$",
    )
    .unwrap()
}

fn cross_episode_re() -> Regex {
    Regex::new(
        r"(?i)^(?P<series>.+?)\s+(?P<season>\d{1,2})x(?P<episode>\d{1,3})\b[\s\-_]*(?P<rest>.*)$",
    )
    .unwrap()
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
    fn parses_season_episode() {
        let parsed = parse_media_name("Harbor Lights S01E03 The Pier.mkv", "tv");
        assert_eq!(parsed.series, "Harbor Lights");
        assert_eq!(parsed.series_index, Some(1003.0));
        assert_eq!(parsed.title, "The Pier");
        assert_eq!(episode_label(1003.0).as_deref(), Some("S1 E3"));
    }

    #[test]
    fn parses_dotted_episode_name() {
        let parsed = parse_media_name("Harbor.Lights.S01E02.mkv", "tv");
        assert_eq!(parsed.series, "Harbor Lights");
        assert_eq!(parsed.series_index, Some(1002.0));
        assert_eq!(parsed.title, "Episode 2");
    }

    #[test]
    fn parses_cross_episode_name() {
        let parsed = parse_media_name("Pilot 1x03.mp4", "tv");
        assert_eq!(parsed.series, "Pilot");
        assert_eq!(parsed.series_index, Some(1003.0));
    }

    #[test]
    fn parses_volume_series() {
        let parsed = parse_media_name("Saga, Vol. 2 - Chapter One.cbz", "comic");
        assert!(parsed.series.to_lowercase().contains("saga"));
        assert_eq!(parsed.series_index, Some(2.0));
    }
}
