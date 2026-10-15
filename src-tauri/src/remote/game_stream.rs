use std::sync::{Arc, Mutex};

use crate::catalog::launch::LaunchPlan;
use crate::config::{AppState, KabinConfig, RemoteHostEntry};
use crate::media_helper::{self, MediaHelperSession};

#[derive(Clone, Default)]
pub struct RemoteGameStreamState {
    active: Arc<Mutex<Option<ActiveStream>>>,
}

struct ActiveStream {
    stop: std::sync::mpsc::Sender<()>,
    title: String,
}

impl RemoteGameStreamState {
    pub fn is_active(&self) -> bool {
        self.active.lock().expect("stream lock").is_some()
    }

    pub fn active_title(&self) -> Option<String> {
        self.active
            .lock()
            .expect("stream lock")
            .as_ref()
            .map(|s| s.title.clone())
    }

    pub fn stop(&self) {
        if let Some(stream) = self.active.lock().expect("stream lock").take() {
            let _ = stream.stop.send(());
        }
    }

    pub fn start(&self, app: &AppState, title_id: &str) -> Result<String, String> {
        if self.is_active() {
            return Err("A remote stream is already active".into());
        }
        let item = app
            .find_item(title_id)
            .ok_or_else(|| "Title not found".to_string())?;
        let LaunchPlan::RemoteGame {
            host_name,
            remote_id,
            ..
        } = item.launch
        else {
            return Err("This title is not a remote game".into());
        };
        let (host, token) = host_and_token(&host_name)?;
        let session = super::client::prepare_remote_session(&host, &token, &remote_id)?;
        let media = session.get("media").cloned().unwrap_or_default();
        if media.get("status").and_then(|v| v.as_str()) == Some("unavailable") {
            return Err(
                media
                    .get("error")
                    .and_then(|v| v.as_str())
                    .unwrap_or("The host media helper is not ready")
                    .to_string(),
            );
        }
        let session_id = session
            .get("id")
            .and_then(|v| v.as_str())
            .ok_or("Host returned an invalid session")?
            .to_string();
        let title = item.title.clone();
        let (stop_tx, stop_rx) = std::sync::mpsc::channel();
        let stream_state = self.clone();

        std::thread::spawn(move || {
            let result = run_client_stream(&host, &token, &session_id, stop_rx);
            if let Err(err) = result {
                eprintln!("Remote game stream ended: {err}");
            }
            let _ = stream_state.active.lock().expect("stream lock").take();
        });

        let mut config = KabinConfig::load();
        config.record_played(title_id);
        let _ = config.save();
        app.invalidate();

        *self.active.lock().expect("stream lock") = Some(ActiveStream {
            stop: stop_tx,
            title: title.clone(),
        });
        Ok(title)
    }
}

fn host_and_token(host_name: &str) -> Result<(RemoteHostEntry, String), String> {
    let config = KabinConfig::load();
    let host = config
        .remote_hosts()
        .into_iter()
        .find(|entry| entry.name == host_name)
        .ok_or_else(|| format!("Remote host “{host_name}” is not paired"))?;
    let token = host
        .token
        .clone()
        .filter(|t| !t.is_empty())
        .ok_or_else(|| "Re-pair required".to_string())?;
    Ok((host, token))
}

fn run_client_stream(
    host: &RemoteHostEntry,
    token: &str,
    session_id: &str,
    stop_rx: std::sync::mpsc::Receiver<()>,
) -> Result<(), String> {
    let mut helper = MediaHelperSession::new("client")?;
    let offer = media_helper::create_client_offer(&mut helper)?;
    let answer = super::client::signal_remote_session(host, token, session_id, &offer)?;
    let sdp = answer
        .get("sdp")
        .and_then(|v| v.as_str())
        .ok_or("The host did not return a stream answer")?;
    helper.send(&serde_json::json!({"type": "answer", "sdp": sdp}))?;
    helper.wait_for("ready")?;
    let _ = super::client::launch_remote_session(host, token, session_id);
    let _ = stop_rx.recv();
    helper.close();
    Ok(())
}

pub fn streaming_available() -> bool {
    media_helper::self_test().unwrap_or(false)
}
