use std::path::Path;
use std::process::Child;
#[cfg(not(windows))]
use std::process::Command;

use crate::catalog::launch::LaunchPlan;

fn launch_desktop(path: &Path) -> Result<(), String> {
    #[cfg(windows)]
    {
        crate::platform::open_path(&path.to_string_lossy())
    }
    #[cfg(not(windows))]
    {
        Command::new("gio")
            .arg("launch")
            .arg(path)
            .spawn()
            .map_err(|e| format!("Could not launch desktop entry: {e}"))?;
        Ok(())
    }
}
pub enum LaunchExecution {
    Detached,
    Tracked(Child),
}

pub fn execute(plan: &LaunchPlan) -> Result<LaunchExecution, String> {
    match plan {
        LaunchPlan::Steam { appid } => {
            crate::platform::spawn_steam_game(appid)?;
            return Ok(LaunchExecution::Detached);
        }
        LaunchPlan::Desktop { desktop_file } => {
            launch_desktop(desktop_file)?;
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
            crate::platform::open_path(&path.to_string_lossy())?;
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
