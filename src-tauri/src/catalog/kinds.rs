pub struct MediaKind {
    pub id: &'static str,
    pub label: &'static str,
    pub plural: &'static str,
    pub aspect: &'static str,
    pub extensions: &'static [&'static str],
}

pub static BOOK: MediaKind = MediaKind {
    id: "book",
    label: "Book",
    plural: "Books",
    aspect: "poster",
    extensions: &[".epub", ".mobi", ".azw", ".azw3", ".fb2", ".txt"],
};

pub static PDF: MediaKind = MediaKind {
    id: "pdf",
    label: "PDF",
    plural: "PDFs",
    aspect: "poster",
    extensions: &[".pdf"],
};

pub static AUDIOBOOK: MediaKind = MediaKind {
    id: "audiobook",
    label: "Audiobook",
    plural: "Audiobooks",
    aspect: "square",
    extensions: &[
        ".m4b", ".aa", ".aax", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".wav",
    ],
};

pub static COMIC: MediaKind = MediaKind {
    id: "comic",
    label: "Comic",
    plural: "Comics",
    aspect: "poster",
    extensions: &[".cbz", ".cbr", ".cb7", ".cbt", ".epub", ".pdf"],
};

pub static MUSIC: MediaKind = MediaKind {
    id: "music",
    label: "Album",
    plural: "Music",
    aspect: "square",
    extensions: &[".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav", ".aac"],
};

pub static VIDEO: MediaKind = MediaKind {
    id: "video",
    label: "Movie",
    plural: "Movies",
    aspect: "widescreen",
    extensions: &[".mkv", ".mp4", ".avi", ".webm", ".mov", ".m4v"],
};

pub static TV: MediaKind = MediaKind {
    id: "tv",
    label: "Episode",
    plural: "TV",
    aspect: "widescreen",
    extensions: &[".mkv", ".mp4", ".avi", ".webm", ".mov", ".m4v"],
};

pub static GAME: MediaKind = MediaKind {
    id: "game",
    label: "Game",
    plural: "Games",
    aspect: "poster",
    extensions: &[],
};

pub const FOLDER_KINDS: [&MediaKind; 7] = [&BOOK, &PDF, &AUDIOBOOK, &COMIC, &MUSIC, &VIDEO, &TV];

pub fn kind_by_id(id: &str) -> &'static MediaKind {
    match id {
        "book" => &BOOK,
        "pdf" => &PDF,
        "audiobook" => &AUDIOBOOK,
        "comic" => &COMIC,
        "music" => &MUSIC,
        "video" => &VIDEO,
        "tv" => &TV,
        _ => &GAME,
    }
}

/// Place a file into a library category. Folder type is the library the user
/// added. A Books folder sorts books, audiobooks, comics, and PDFs. A Video
/// folder (`screen`) sorts movies and TV episodes.
pub fn classify_file(folder_type: &str, ext: &str, file_name: &str) -> Option<&'static str> {
    let ext = normalize_ext(ext);
    match folder_type {
        "music" => extension_matches(&MUSIC, &ext).then_some("music"),
        "audiobook" => extension_matches(&AUDIOBOOK, &ext).then_some("audiobook"),
        "comic" => {
            (extension_matches(&COMIC, &ext) || ext == ".pdf" || ext == ".epub").then_some("comic")
        }
        "pdf" => (ext == ".pdf").then_some("pdf"),
        "book" => classify_reading(&ext),
        "tv" => extension_matches(&VIDEO, &ext).then_some("tv"),
        "video" => extension_matches(&VIDEO, &ext).then_some("video"),
        "screen" => {
            if !extension_matches(&VIDEO, &ext) {
                return None;
            }
            if looks_like_episode(file_name) {
                Some("tv")
            } else {
                Some("video")
            }
        }
        _ => None,
    }
}

fn classify_reading(ext: &str) -> Option<&'static str> {
    match ext {
        ".pdf" => Some("pdf"),
        ".cbz" | ".cbr" | ".cb7" | ".cbt" => Some("comic"),
        ".m4b" | ".aa" | ".aax" => Some("audiobook"),
        ".epub" | ".mobi" | ".azw" | ".azw3" | ".fb2" | ".txt" => Some("book"),
        _ => None,
    }
}

fn normalize_ext(ext: &str) -> String {
    let trimmed = ext.trim().trim_start_matches('.').to_ascii_lowercase();
    if trimmed.is_empty() {
        String::new()
    } else {
        format!(".{trimmed}")
    }
}

pub fn looks_like_episode(name: &str) -> bool {
    let lower = name.to_ascii_lowercase();
    let bytes = lower.as_bytes();
    let n = bytes.len();
    for i in 0..n {
        if bytes[i] != b's' {
            continue;
        }
        let mut j = i + 1;
        let mut season_digits = 0;
        while j < n && bytes[j].is_ascii_digit() && season_digits < 3 {
            season_digits += 1;
            j += 1;
        }
        if !(1..=2).contains(&season_digits) || j >= n || bytes[j] != b'e' {
            continue;
        }
        j += 1;
        let mut episode_digits = 0;
        while j < n && bytes[j].is_ascii_digit() && episode_digits < 4 {
            episode_digits += 1;
            j += 1;
        }
        if (1..=3).contains(&episode_digits) {
            return true;
        }
    }
    for i in 0..n {
        if !bytes[i].is_ascii_digit() {
            continue;
        }
        if i > 0 && bytes[i - 1].is_ascii_alphanumeric() {
            continue;
        }
        let mut j = i;
        let mut left = 0;
        while j < n && bytes[j].is_ascii_digit() && left < 3 {
            left += 1;
            j += 1;
        }
        if !(1..=2).contains(&left) || j >= n || bytes[j] != b'x' {
            continue;
        }
        j += 1;
        let mut right = 0;
        while j < n && bytes[j].is_ascii_digit() && right < 4 {
            right += 1;
            j += 1;
        }
        if (1..=3).contains(&right) {
            return true;
        }
    }
    false
}

pub fn extension_matches(kind: &MediaKind, ext: &str) -> bool {
    kind.extensions.iter().any(|candidate| candidate.eq_ignore_ascii_case(ext))
}

pub fn accent_hue(kind_id: &str) -> u16 {
    match kind_id {
        "game" => 32,
        "book" => 38,
        "pdf" => 28,
        "audiobook" => 48,
        "comic" => 14,
        "music" => 145,
        "video" => 195,
        "tv" => 210,
        _ => 220,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn books_folder_sorts_formats() {
        assert_eq!(classify_file("book", ".pdf", "Notes.pdf"), Some("pdf"));
        assert_eq!(classify_file("book", "epub", "Dune.epub"), Some("book"));
        assert_eq!(classify_file("book", ".cbz", "Saga.cbz"), Some("comic"));
        assert_eq!(classify_file("book", ".m4b", "Dune.m4b"), Some("audiobook"));
        assert_eq!(classify_file("book", ".mp3", "track.mp3"), None);
    }

    #[test]
    fn video_folder_sorts_episodes() {
        assert_eq!(
            classify_file("screen", ".mkv", "Show.S01E02.mkv"),
            Some("tv")
        );
        assert_eq!(classify_file("screen", ".mp4", "Pilot 1x03.mp4"), Some("tv"));
        assert_eq!(
            classify_file("screen", ".mkv", "Dune.2021.mkv"),
            Some("video")
        );
        assert_eq!(
            classify_file("video", ".mkv", "Show.S01E02.mkv"),
            Some("video")
        );
        assert_eq!(classify_file("tv", ".mkv", "Loose.mkv"), Some("tv"));
    }
}
