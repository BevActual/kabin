use std::process::{Child, Command};

use crate::catalog::launch::LaunchPlan;
use crate::config::KabinConfig;

pub enum LaunchExecution {
    Detached,
    Tracked(Child),
}

pub fn execute(plan: &LaunchPlan) -> Result<LaunchExecution, String> {
    match plan {
        LaunchPlan::Steam { appid } => {
            Command::new("steam")
                .arg(format!("steam://rungameid/{appid}"))
                .spawn()
                .map_err(|e| format!("Could not start Steam: {e}"))?;
            return Ok(LaunchExecution::Detached);
        }
        LaunchPlan::Desktop { desktop_file } => {
            Command::new("gio")
                .arg("launch")
                .arg(desktop_file)
                .spawn()
                .map_err(|e| format!("Could not launch desktop entry: {e}"))?;
            return Ok(LaunchExecution::Detached);
        }
        LaunchPlan::Command {
            argv,
            emulator_id,
            bios_path,
        } => {
            if let (Some(id), Some(path)) = (emulator_id.as_deref(), bios_path.as_deref()) {
                let _ = crate::emulators::bios::prepare_bios_env(id, path);
            }
            let child = crate::emulators::spawn_detached(argv, None)?;
            return Ok(LaunchExecution::Tracked(child));
        }
        LaunchPlan::OpenPath { path } => {
            Command::new("xdg-open")
                .arg(path)
                .spawn()
                .map_err(|e| format!("Could not open file: {e}"))?;
            return Ok(LaunchExecution::Detached);
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
}

pub fn touch_recent(config: &mut KabinConfig, title_id: &str) {
    config.touch_recent(title_id);
}
