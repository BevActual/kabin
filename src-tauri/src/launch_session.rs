use std::process::Child;
use std::sync::Mutex;
use std::time::Instant;

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager};

use crate::config::{AppState, KabinConfig};
use crate::sessions::{quick_failure_message, recordable_seconds};

#[derive(Clone, Default)]
pub struct LaunchSessionState {
    active: std::sync::Arc<Mutex<Option<String>>>,
}

impl LaunchSessionState {
    pub fn is_active(&self) -> bool {
        self.active
            .lock()
            .expect("launch session lock")
            .is_some()
    }

    pub fn start_monitor(
        &self,
        app: AppHandle,
        state: AppState,
        game_id: String,
        title: String,
        mut child: Child,
    ) {
        {
            let mut guard = self.active.lock().expect("launch session lock");
            *guard = Some(game_id.clone());
        }
        if let Some(window) = app
            .webview_windows()
            .values()
            .next()
            .cloned()
        {
            let _ = window.minimize();
        }

        let session_state = self.clone();
        std::thread::spawn(move || {
            let started = Instant::now();
            let status = child.wait();
            let elapsed = started.elapsed().as_secs_f64();
            let code = status.ok().and_then(|s| s.code());
            let seconds = recordable_seconds(elapsed);
            if seconds > 0 {
                let mut config = KabinConfig::load();
                config.record_play_time(&game_id, seconds);
                let _ = config.save();
            }
            state.invalidate();
            let message = quick_failure_message(&title, code, elapsed);
            let payload = GameSessionFinished {
                game_id: game_id.clone(),
                title: title.clone(),
                elapsed_seconds: elapsed.floor() as u64,
                recorded_seconds: seconds,
                exit_code: code,
                message: message.clone(),
            };
            let _ = app.emit("game-session-finished", &payload);
            if let Some(window) = app.webview_windows().values().next() {
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
            let mut guard = session_state.active.lock().expect("launch session lock");
            *guard = None;
        });
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GameSessionFinished {
    pub game_id: String,
    pub title: String,
    pub elapsed_seconds: u64,
    pub recorded_seconds: u64,
    pub exit_code: Option<i32>,
    pub message: Option<String>,
}
