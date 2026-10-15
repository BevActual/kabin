pub fn tidy_filename(name: &str) -> String {
    let mut text = name.replace('_', " ");
    if let Some(stem) = text.rsplit_once('.') {
        if stem.1.len() <= 5 {
            text = stem.0.to_string();
        }
    }
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}
