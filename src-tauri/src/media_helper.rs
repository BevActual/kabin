use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{self, RecvTimeoutError};
use std::time::{Duration, Instant};

use serde_json::Value;

const WAIT_TIMEOUT: Duration = Duration::from_secs(12);

pub fn native_helper_path() -> Option<PathBuf> {
    if let Ok(manifest) = std::env::var("CARGO_MANIFEST_DIR") {
        let built = PathBuf::from(manifest)
            .join("..")
            .join("build")
            .join("kabin-media-helper");
        if built.is_file() {
            use std::os::unix::fs::PermissionsExt;
            if built.metadata().ok()?.permissions().mode() & 0o111 != 0 {
                return Some(built);
            }
        }
    }
    which_helper("kabin-media-helper")
}

fn which_helper(name: &str) -> Option<PathBuf> {
    Command::new("which")
        .arg(name)
        .output()
        .ok()
        .filter(|o| o.status.success())
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .map(|s| PathBuf::from(s.trim()))
        .filter(|p| !p.as_os_str().is_empty())
}

pub fn self_test() -> Result<bool, String> {
    let Some(path) = native_helper_path() else {
        return Ok(false);
    };
    let output = Command::new(&path)
        .arg("--self-test")
        .output()
        .map_err(|e| e.to_string())?;
    if !output.status.success() {
        return Ok(false);
    }
    let payload: Value = serde_json::from_slice(&output.stdout).unwrap_or(Value::Null);
    Ok(payload.get("ok").and_then(|v| v.as_bool()).unwrap_or(false))
}

pub fn stream_offer() -> Value {
    match self_test() {
        Ok(true) => serde_json::json!({
            "status": "awaiting-negotiation",
            "protocol": "kabin",
            "transport": "webrtc",
        }),
        _ => serde_json::json!({
            "status": "unavailable",
            "protocol": "kabin",
            "transport": "webrtc",
            "error": "Kabin media helper is not ready",
        }),
    }
}

pub struct MediaHelperSession {
    child: Child,
    stdin: std::process::ChildStdin,
    rx: mpsc::Receiver<Value>,
    stderr_tail: std::sync::Arc<std::sync::Mutex<Vec<String>>>,
}

impl MediaHelperSession {
    pub fn new(role: &str) -> Result<Self, String> {
        let path = native_helper_path().ok_or("Kabin media helper is not built")?;
        let mut child = Command::new(path)
            .arg("--session")
            .arg(role)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to start media helper: {e}"))?;
        let stdin = child
            .stdin
            .take()
            .ok_or("media helper stdin is closed")?;
        let stdout = child
            .stdout
            .take()
            .ok_or("media helper stdout is closed")?;
        let stderr = child.stderr.take();
        let (tx, rx) = mpsc::channel();
        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines().map_while(Result::ok) {
                let line = line.trim();
                if line.is_empty() {
                    continue;
                }
                let event: Value = serde_json::from_str(line)
                    .unwrap_or_else(|_| serde_json::json!({"type": "error", "sdp": line}));
                let _ = tx.send(event);
            }
        });
        let stderr_tail = std::sync::Arc::new(std::sync::Mutex::new(Vec::new()));
        if let Some(stderr) = stderr {
            let tail = stderr_tail.clone();
            std::thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines().map_while(Result::ok) {
                    let line = line.trim().to_string();
                    if line.is_empty() {
                        continue;
                    }
                    let mut guard = tail.lock().expect("stderr tail");
                    guard.push(line);
                    if guard.len() > 20 {
                        let drain = guard.len() - 20;
                        guard.drain(0..drain);
                    }
                }
            });
        }
        Ok(Self {
            child,
            stdin,
            rx,
            stderr_tail,
        })
    }

    fn stderr_message(&self) -> String {
        let guard = self.stderr_tail.lock().expect("stderr tail");
        if guard.is_empty() {
            return String::new();
        }
        format!(" · {}", guard.iter().rev().take(3).cloned().collect::<Vec<_>>().join(" | "))
    }

    pub fn send(&mut self, payload: &Value) -> Result<(), String> {
        let line = serde_json::to_string(payload).map_err(|e| e.to_string())?;
        writeln!(self.stdin, "{line}").map_err(|e| e.to_string())?;
        self.stdin.flush().map_err(|e| e.to_string())
    }

    pub fn wait_for(&mut self, message_type: &str) -> Result<Value, String> {
        let deadline = Instant::now() + WAIT_TIMEOUT;
        loop {
            let remaining = deadline.saturating_duration_since(Instant::now());
            if remaining.is_zero() {
                return Err(format!(
                    "timed out waiting for {message_type}{}",
                    self.stderr_message()
                ));
            }
            match self.rx.recv_timeout(remaining.min(Duration::from_millis(200))) {
                Ok(event) => {
                    if event.get("type").and_then(|v| v.as_str()) == Some("error") {
                        return Err(event
                            .get("sdp")
                            .and_then(|v| v.as_str())
                            .unwrap_or("media helper error")
                            .to_string());
                    }
                    if event.get("type").and_then(|v| v.as_str()) == Some(message_type) {
                        return Ok(event);
                    }
                }
                Err(RecvTimeoutError::Timeout) => {
                    if self.child.try_wait().ok().flatten().is_some() {
                        return Err(format!(
                            "media helper exited{}",
                            self.stderr_message()
                        ));
                    }
                }
                Err(RecvTimeoutError::Disconnected) => {
                    return Err(format!(
                        "media helper disconnected{}",
                        self.stderr_message()
                    ));
                }
            }
        }
    }

    pub fn close(&mut self) {
        let _ = self.send(&serde_json::json!({"type": "close"}));
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

pub fn answer_host_offer(session: &mut MediaHelperSession, offer_sdp: &str) -> Result<String, String> {
    session.wait_for("hello")?;
    session.send(&serde_json::json!({"type": "offer", "sdp": offer_sdp}))?;
    let answer = session.wait_for("answer")?;
    answer
        .get("sdp")
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .ok_or_else(|| "host helper produced no answer".into())
}

pub fn create_client_offer(session: &mut MediaHelperSession) -> Result<String, String> {
    session.wait_for("hello")?;
    let offer = session.wait_for("offer")?;
    offer
        .get("sdp")
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .ok_or_else(|| "client helper produced no offer".into())
}
