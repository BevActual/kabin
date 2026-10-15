use crate::catalog::reader::{build_reader_session, ReaderSession};
use crate::config::{AppState, KabinConfig};

#[tauri::command]
pub fn get_reader_session(
    state: tauri::State<'_, AppState>,
    title_id: String,
) -> Option<ReaderSession> {
    let _ = state.snapshot(false);
    let item = state.find_item(&title_id)?;
    build_reader_session(&item, &KabinConfig::load())
}

#[tauri::command]
pub fn save_reader_progress(
    title_id: String,
    page: u32,
    total: u32,
    scroll: Option<f64>,
) -> Result<(), String> {
    let mut config = KabinConfig::load();
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0);
    let progress = config
        .data
        .as_object_mut()
        .expect("config")
        .entry("progress")
        .or_insert_with(|| serde_json::json!({}));
    if let Some(obj) = progress.as_object_mut() {
        let mut payload = serde_json::json!({
            "position": page,
            "duration": total.max(1),
            "track": 0,
            "updated_at": now,
        });
        if let Some(scroll) = scroll {
            if let Some(map) = payload.as_object_mut() {
                map.insert(
                    "scroll".into(),
                    serde_json::json!(scroll.clamp(0.0, 1.0)),
                );
            }
        }
        obj.insert(title_id, payload);
    }
    config.save()
}
