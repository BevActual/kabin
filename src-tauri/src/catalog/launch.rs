use std::path::PathBuf;

#[derive(Debug, Clone)]
pub enum LaunchPlan {
    Steam { appid: String },
    Desktop { desktop_file: PathBuf },
    Command {
        argv: Vec<String>,
    },
    OpenPath { path: PathBuf },
    RemoteGame {
        host_name: String,
        remote_id: String,
        playable: bool,
    },
    RemoteStream {
        host_name: String,
        remote_id: String,
        playable: bool,
        size: u64,
    },
}

impl LaunchPlan {
    pub fn is_available(&self) -> bool {
        true
    }
}
