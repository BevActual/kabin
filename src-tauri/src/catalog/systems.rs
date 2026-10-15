pub struct SystemDefinition {
    pub id: &'static str,
    pub name: &'static str,
    pub extensions: &'static [&'static str],
}

pub const SYSTEMS: &[SystemDefinition] = &[
    SystemDefinition {
        id: "nes",
        name: "Nintendo Entertainment System",
        extensions: &["nes", "fds", "zip"],
    },
    SystemDefinition {
        id: "snes",
        name: "Super Nintendo",
        extensions: &["sfc", "smc", "fig", "zip"],
    },
    SystemDefinition {
        id: "n64",
        name: "Nintendo 64",
        extensions: &["z64", "n64", "v64", "zip"],
    },
    SystemDefinition {
        id: "gb",
        name: "Game Boy",
        extensions: &["gb", "zip"],
    },
    SystemDefinition {
        id: "gbc",
        name: "Game Boy Color",
        extensions: &["gbc", "zip"],
    },
    SystemDefinition {
        id: "gba",
        name: "Game Boy Advance",
        extensions: &["gba", "zip"],
    },
    SystemDefinition {
        id: "genesis",
        name: "Sega Genesis / Mega Drive",
        extensions: &["md", "gen", "smd", "32x", "zip"],
    },
    SystemDefinition {
        id: "ps1",
        name: "PlayStation",
        extensions: &["cue", "chd", "pbp", "iso"],
    },
    SystemDefinition {
        id: "ps2",
        name: "PlayStation 2",
        extensions: &["iso", "chd", "cso"],
    },
    SystemDefinition {
        id: "psp",
        name: "PlayStation Portable",
        extensions: &["iso", "cso", "pbp"],
    },
    SystemDefinition {
        id: "gamecube",
        name: "Nintendo GameCube",
        extensions: &["iso", "gcm", "rvz", "wia"],
    },
    SystemDefinition {
        id: "wii",
        name: "Nintendo Wii",
        extensions: &["iso", "wbfs", "rvz", "wia"],
    },
    SystemDefinition {
        id: "arcade",
        name: "Arcade",
        extensions: &["zip", "7z"],
    },
];

pub fn get_system(system_id: &str) -> Option<&'static SystemDefinition> {
    SYSTEMS.iter().find(|s| s.id == system_id)
}
