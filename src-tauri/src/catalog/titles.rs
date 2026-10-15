use regex::Regex;

pub fn tidy_filename(name: &str) -> String {
    let mut text = name.replace('_', " ");
    if let Some(stem) = text.rsplit_once('.') {
        if stem.1.len() <= 5 {
            text = stem.0.to_string();
        }
    }
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

pub fn clean_game_title(filename: &str) -> String {
    let tag = Regex::new(r"\s*[\[(][^\])]*[\])]\s*").unwrap();
    let mut title = std::path::Path::new(filename)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or(filename)
        .replace('_', " ")
        .trim()
        .to_string();
    title = tag.replace_all(&title, " ").to_string();
    title = title.split_whitespace().collect::<Vec<_>>().join(" ");
    title.trim_end().trim_end_matches('-').trim().to_string()
}
