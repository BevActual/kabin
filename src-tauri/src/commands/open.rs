use std::process::Command;

#[tauri::command]
pub fn open_external_path(path: String) -> Result<(), String> {
    Command::new("xdg-open")
        .arg(path)
        .spawn()
        .map_err(|e| e.to_string())?;
    Ok(())
}
