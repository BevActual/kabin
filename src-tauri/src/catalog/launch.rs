use std::path::PathBuf;

#[derive(Debug, Clone)]
pub enum LaunchPlan {
    Steam { appid: String },
    Desktop { desktop_file: PathBuf },
    Command {
        argv: Vec<String>,
    },
    OpenPath { path: PathBuf },
}

impl LaunchPlan {
    pub fn is_available(&self) -> bool {
        true
    }
}
