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
    extensions: &[".epub", ".pdf", ".mobi", ".azw3", ".fb2", ".txt"],
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

pub const FOLDER_KINDS: [&MediaKind; 5] = [&BOOK, &COMIC, &MUSIC, &VIDEO, &TV];

pub fn kind_by_id(id: &str) -> &'static MediaKind {
    match id {
        "book" => &BOOK,
        "comic" => &COMIC,
        "music" => &MUSIC,
        "video" => &VIDEO,
        "tv" => &TV,
        _ => &GAME,
    }
}

pub fn extension_matches(kind: &MediaKind, ext: &str) -> bool {
    kind.extensions.iter().any(|candidate| candidate.eq_ignore_ascii_case(ext))
}

pub fn accent_hue(kind_id: &str) -> u16 {
    match kind_id {
        "game" => 32,
        "book" => 38,
        "comic" => 14,
        "music" => 145,
        "video" => 195,
        "tv" => 210,
        _ => 220,
    }
}
