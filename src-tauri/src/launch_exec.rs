use std::process::Command;

use crate::catalog::launch::LaunchPlan;
use crate::config::KabinConfig;

pub fn execute(plan: &LaunchPlan) -> Result<(), String> {
    match plan {
        LaunchPlan::Steam { appid } => {
            Command::new("steam")
                .arg(format!("steam://rungameid/{appid}"))
                .spawn()
                .map_err(|e| format!("Could not start Steam: {e}"))?;
        }
        LaunchPlan::Desktop { desktop_file } => {
            Command::new("gio")
                .arg("launch")
                .arg(desktop_file)
                .spawn()
                .map_err(|e| format!("Could not launch desktop entry: {e}"))?;
        }
        LaunchPlan::Command { argv } => {
            crate::emulators::spawn_detached(argv, None)?;
        }
        LaunchPlan::OpenPath { path } => {
            Command::new("xdg-open")
                .arg(path)
                .spawn()
                .map_err(|e| format!("Could not open file: {e}"))?;
        }
        LaunchPlan::RemoteGame { .. } => {
            return Err(
                "Remote game streaming is not available in the Tauri app yet. Use python3 -m kabin."
                    .into(),
            );
        }
        LaunchPlan::RemoteStream { .. } => {
            return Err("Open this title in the player or reader.".into());
        }
    }
    Ok(())
}

pub fn touch_recent(config: &mut KabinConfig, title_id: &str) {
    config.touch_recent(title_id);
}
