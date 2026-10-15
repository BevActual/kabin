pub mod bios;
pub mod detect;
pub mod managed;

use std::path::Path;
use std::process::Command;

use serde_json::Value;

pub fn emulator_command(profile: &Value) -> Result<Vec<String>, String> {
    let runtime = profile
        .get("runtime")
        .and_then(|v| v.as_str())
        .unwrap_or("native");
    let executable = profile
        .get("executable")
        .and_then(|v| v.as_str())
        .ok_or("Emulator executable is missing")?;
    if runtime == "native" || runtime == "managed" {
        Ok(vec![executable.to_string()])
    } else if runtime == "flatpak" {
        Ok(vec![
            "flatpak".into(),
            "run".into(),
            executable.to_string(),
        ])
    } else {
        Err(format!("Unknown emulator runtime: {runtime}"))
    }
}

fn flag01(value: bool) -> &'static str {
    if value { "1" } else { "0" }
}

fn with_rom(mut command: Vec<String>, rom_path: &Path) -> Vec<String> {
    command.push(rom_path.to_string_lossy().into_owned());
    command
}

fn emulation_options(settings: Option<&Value>) -> (bool, bool, bool, bool) {
    let Some(settings) = settings else {
        return (false, false, false, false);
    };
    (
        settings.get("fullscreen").and_then(|v| v.as_bool()).unwrap_or(false),
        settings.get("vsync").and_then(|v| v.as_bool()).unwrap_or(false),
        settings
            .get("integer_scaling")
            .and_then(|v| v.as_bool())
            .unwrap_or(false),
        settings.get("rewind").and_then(|v| v.as_bool()).unwrap_or(false),
    )
}

pub fn build_command(
    profile: &Value,
    rom_path: &Path,
    settings: Option<&Value>,
) -> Result<Vec<String>, String> {
    let mut command = emulator_command(profile)?;
    let emulator_id = profile.get("id").and_then(|v| v.as_str()).unwrap_or("");
    let (fullscreen, vsync, integer_scaling, rewind) = emulation_options(settings);

    match emulator_id {
        "fceux" if settings.is_some() => {
            command.extend(["--fullscreen".into(), flag01(fullscreen).into()]);
            if integer_scaling {
                command.extend([
                    "--autoscale".into(),
                    "0".into(),
                    "--xstretch".into(),
                    "0".into(),
                    "--ystretch".into(),
                    "0".into(),
                ]);
            } else {
                command.extend([
                    "--autoscale".into(),
                    "1".into(),
                    "--keepratio".into(),
                    "1".into(),
                ]);
            }
            Ok(with_rom(command, rom_path))
        }
        "mgba" if settings.is_some() => {
            if fullscreen {
                command.push("-f".into());
            }
            command.extend([
                "-C".into(),
                format!("videoSync={}", flag01(vsync)),
                "-C".into(),
                format!("rewindEnable={}", flag01(rewind)),
                "-C".into(),
                "lockAspectRatio=1".into(),
                "-C".into(),
                format!("lockIntegerScaling={}", flag01(integer_scaling)),
            ]);
            Ok(with_rom(command, rom_path))
        }
        "dolphin" => {
            command.extend(["--batch".into(), "--exec".into()]);
            Ok(with_rom(command, rom_path))
        }
        "duckstation" | "pcsx2" => {
            command.push("-batch".into());
            if fullscreen {
                command.push("-fullscreen".into());
            }
            Ok(with_rom(command, rom_path))
        }
        "mame" => {
            command.extend([
                "-rompath".into(),
                rom_path
                    .parent()
                    .map(|p| p.to_string_lossy().into_owned())
                    .unwrap_or_default(),
            ]);
            command.push(
                rom_path
                    .file_stem()
                    .map(|s| s.to_string_lossy().into_owned())
                    .unwrap_or_default(),
            );
            Ok(command)
        }
        _ => {
            if fullscreen {
                let flag = match emulator_id {
                    "blastem" => Some("-f"),
                    "punes" | "mesen" => Some("--fullscreen"),
                    _ => None,
                };
                if let Some(flag) = flag {
                    command.push(flag.into());
                }
            }
            Ok(with_rom(command, rom_path))
        }
    }
}

pub fn custom_command(template: &str, rom_path: &Path) -> Result<Vec<String>, String> {
    if !template.contains("{rom}") {
        return Err("Custom emulator command must include {rom}".into());
    }
    let parts = shell_words::split(template).map_err(|e| e.to_string())?;
    Ok(parts
        .into_iter()
        .map(|part| part.replace("{rom}", &rom_path.to_string_lossy()))
        .collect())
}

pub fn spawn_detached(command: &[String], env: Option<&[(String, String)]>) -> Result<(), String> {
    if command.is_empty() {
        return Err("Empty command".into());
    }
    let program = &command[0];
    let mut cmd = Command::new(program);
    cmd.args(&command[1..]);
    if let Some(pairs) = env {
        for (key, value) in pairs {
            cmd.env(key, value);
        }
    }
    cmd.spawn()
        .map_err(|e| format!("Failed to launch {program}: {e}"))?;
    Ok(())
}
