use std::path::PathBuf;

#[derive(Debug, Clone)]
pub enum LaunchPlan {
    Steam { appid: String },
    Desktop { desktop_file: PathBuf },
    Command {
        argv: Vec<String>,
        emulator_id: Option<String>,
        bios_path: Option<PathBuf>,
    },
    OpenPath { path: PathBuf },
    RemoteGame {
        host_name: String,
        remote_id: String,
        playable: bool,
        has_artwork: bool,
        appid: String,
    },
    RemoteStream {
        host_name: String,
        remote_id: String,
        playable: bool,
        size: u64,
        has_artwork: bool,
    },
}

impl LaunchPlan {
    pub fn is_available(&self) -> bool {
        true
    }
}
