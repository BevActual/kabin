use std::collections::HashMap;
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use rand::Rng;
use serde_json::{json, Value};

use crate::catalog::item::LibraryItem;
use crate::catalog::launch::LaunchPlan;
use crate::config::KabinConfig;
use crate::launch_exec::{execute, LaunchExecution};
use crate::media_helper::{self, MediaHelperSession};

const SESSION_TTL: f64 = 600.0;
const MAX_SESSIONS: usize = 32;

pub struct SessionStore {
    inner: Mutex<Inner>,
}

struct Inner {
    sessions: HashMap<String, Value>,
    games: HashMap<String, String>,
    helpers: HashMap<String, MediaHelperSession>,
}

impl Default for SessionStore {
    fn default() -> Self {
        Self {
            inner: Mutex::new(Inner {
                sessions: HashMap::new(),
                games: HashMap::new(),
                helpers: HashMap::new(),
            }),
        }
    }
}

impl SessionStore {
    pub fn prepare(&self, item: &LibraryItem) -> Option<Value> {
        if !item.can_launch() || matches!(item.launch, LaunchPlan::RemoteGame { .. }) {
            return None;
        }
        let session_id = new_session_id();
        let media = media_helper::stream_offer();
        let state = if media.get("status").and_then(|v| v.as_str()) == Some("ready") {
            "ready"
        } else {
            "prepared"
        };
        let helper_ready = media_helper::self_test().unwrap_or(false);
        let session = json!({
            "id": session_id,
            "game_id": item.id,
            "title": item.title,
            "state": state,
            "created_at": now_secs(),
            "media": media,
            "capabilities": {
                "webrtc": helper_ready,
                "backend": if helper_ready { "kabin" } else { "none" },
            },
        });
        let mut guard = self.inner.lock().expect("sessions lock");
        guard.sessions.insert(session_id.clone(), session.clone());
        guard.games.insert(session_id, item.id.clone());
        drop_stale_locked(&mut guard);
        Some(session)
    }

    pub fn get(&self, session_id: &str) -> Option<Value> {
        let mut guard = self.inner.lock().expect("sessions lock");
        drop_stale_locked(&mut guard);
        guard.sessions.get(session_id).cloned()
    }

    pub fn negotiate(&self, session_id: &str, offer_sdp: &str) -> Result<String, String> {
        if self.get(session_id).is_none() {
            return Err("session not found".into());
        }
        let mut helper = MediaHelperSession::new("host")?;
        let answer = media_helper::answer_host_offer(&mut helper, offer_sdp)?;
        let mut guard = self.inner.lock().expect("sessions lock");
        guard.helpers.remove(session_id);
        guard.helpers.insert(session_id.to_string(), helper);
        if let Some(session) = guard.sessions.get_mut(session_id) {
            if let Some(obj) = session.as_object_mut() {
                if let Some(media) = obj.get_mut("media").and_then(|m| m.as_object_mut()) {
                    media.insert("status".into(), json!("connected"));
                }
                obj.insert("state".into(), json!("ready"));
            }
        }
        Ok(answer)
    }

    pub fn activate(&self, session_id: &str, app: &crate::config::AppState) -> Result<Value, String> {
        let snapshot = {
            let guard = self.inner.lock().expect("sessions lock");
            guard.sessions.get(session_id).cloned()
        };
        let Some(session) = snapshot else {
            return Err("session not found or expired".into());
        };
        let media_status = session
            .get("media")
            .and_then(|m| m.get("status"))
            .and_then(|v| v.as_str())
            .unwrap_or("");
        if media_status != "connected" {
            return Err("media channel is not connected".into());
        }
        if session.get("state").and_then(|v| v.as_str()) == Some("running") {
            return Ok(session);
        }
        let game_id = {
            let guard = self.inner.lock().expect("sessions lock");
            guard.games.get(session_id).cloned()
        };
        let Some(game_id) = game_id else {
            return Err("game is no longer launchable".into());
        };
        let plan = app
            .launch_plan(&game_id)
            .ok_or_else(|| "game is no longer launchable".to_string())?;
        match execute(&plan)? {
            LaunchExecution::Detached => {}
            LaunchExecution::Tracked(mut child) => {
                std::thread::spawn(move || {
                    let _ = child.wait();
                });
            }
        }
        let mut config = KabinConfig::load();
        config.record_played(&game_id);
        config.save()?;
        app.invalidate();
        let mut guard = self.inner.lock().expect("sessions lock");
        if let Some(entry) = guard.sessions.get_mut(session_id) {
            if let Some(obj) = entry.as_object_mut() {
                obj.insert("state".into(), json!("running"));
                obj.insert("started_at".into(), json!(now_secs()));
            }
            return Ok(entry.clone());
        }
        Err("session not found".into())
    }
}

fn new_session_id() -> String {
    let bytes: [u8; 18] = rand::thread_rng().gen();
    URL_SAFE_NO_PAD.encode(bytes)
}

fn now_secs() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

fn drop_stale_locked(inner: &mut Inner) {
    let now = now_secs();
    let expired: Vec<String> = inner
        .sessions
        .iter()
        .filter(|(_, session)| {
            session
                .get("created_at")
                .and_then(|v| v.as_f64())
                .is_some_and(|created| now - created > SESSION_TTL)
        })
        .map(|(id, _)| id.clone())
        .collect();
    for id in expired {
        inner.sessions.remove(&id);
        inner.games.remove(&id);
        inner.helpers.remove(&id);
    }
    if inner.sessions.len() <= MAX_SESSIONS {
        return;
    }
    let mut live: Vec<(String, f64)> = inner
        .sessions
        .iter()
        .map(|(id, session)| {
            (
                id.clone(),
                session
                    .get("created_at")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0),
            )
        })
        .collect();
    live.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
    let drop_count = inner.sessions.len().saturating_sub(MAX_SESSIONS);
    for (id, _) in live.into_iter().take(drop_count) {
        inner.sessions.remove(&id);
        inner.games.remove(&id);
        inner.helpers.remove(&id);
    }
}
