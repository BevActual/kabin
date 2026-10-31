#[tauri::command]
pub fn open_external_path(path: String) -> Result<(), String> {
    crate::platform::open_path(&path)
}
