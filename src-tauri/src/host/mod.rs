mod artwork;
mod catalog;
mod cert;
mod pairing;
pub mod sessions;
mod server;

use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;

use serde::Serialize;

use crate::config::{AppState, KabinConfig};

pub struct HostController {
    join: Option<JoinHandle<()>>,
    shutdown: Option<tokio::sync::oneshot::Sender<()>>,
    avahi: Option<std::process::Child>,
    pub fingerprint: String,
    pub error: Option<String>,
    pairing: Arc<Mutex<pairing::PairingState>>,
}

impl Default for HostController {
    fn default() -> Self {
        Self {
            join: None,
            shutdown: None,
            avahi: None,
            fingerprint: String::new(),
            error: None,
            pairing: Arc::new(Mutex::new(pairing::PairingState::default())),
        }
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HostStatus {
    pub running: bool,
    pub enabled: bool,
    pub port: u16,
    pub host_name: String,
    pub fingerprint: String,
    pub pairing_code: Option<String>,
    pub pairing_expires_at: Option<f64>,
    pub error: Option<String>,
}

pub fn sync_host(app_state: &AppState, host: &Mutex<HostController>) {
    let mut config = KabinConfig::load();
    let mut controller = host.lock().expect("host lock");
    if !config.host_enabled() {
        controller.stop();
        return;
    }
    if let Err(err) = config.ensure_network_token() {
        controller.error = Some(err);
        controller.stop();
        return;
    }
    if controller.join.is_some() && controller.error.is_none() {
        return;
    }
    controller.stop();
    match cert::ensure_host_certificate() {
        Ok((_cert, _key, fingerprint)) => {
            controller.fingerprint = fingerprint.clone();
            let pairing = controller.pairing.clone();
            let state = app_state.clone();
            let (tx, rx) = tokio::sync::oneshot::channel();
            let port = config.host_port();
            let host_name = config.host_name();
            let host_for_server = host_name.clone();
            let fp = fingerprint.clone();
            let join = std::thread::spawn(move || {
                let rt = tokio::runtime::Builder::new_multi_thread()
                    .enable_all()
                    .build()
                    .expect("tokio runtime");
                rt.block_on(async move {
                    if let Err(err) = server::run(state, pairing, port, host_for_server, rx).await {
                        eprintln!("Kabin host stopped: {err}");
                    }
                });
            });
            controller.join = Some(join);
            controller.shutdown = Some(tx);
            controller.error = None;
            controller.avahi = publish_avahi(&host_name, port, &fp);
        }
        Err(err) => {
            controller.error = Some(err);
        }
    }
}

fn publish_avahi(name: &str, port: u16, fingerprint: &str) -> Option<std::process::Child> {
    Command::new("avahi-publish-service")
        .args([
            name,
            "_kabin._tcp",
            &port.to_string(),
            "protocol=1",
            "tls=1",
            &format!("fingerprint={fingerprint}"),
        ])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .ok()
}

impl HostController {
    pub fn stop(&mut self) {
        if let Some(tx) = self.shutdown.take() {
            let _ = tx.send(());
        }
        if let Some(handle) = self.join.take() {
            let _ = handle.join();
        }
        if let Some(mut child) = self.avahi.take() {
            let _ = child.kill();
        }
    }

    pub fn status(&self, config: &KabinConfig) -> HostStatus {
        let pairing = self.pairing.lock().expect("pairing lock");
        HostStatus {
            running: self.join.is_some() && self.error.is_none(),
            enabled: config.host_enabled(),
            port: config.host_port(),
            host_name: config.host_name(),
            fingerprint: self.fingerprint.clone(),
            pairing_code: pairing.code.clone(),
            pairing_expires_at: pairing.expires_at,
            error: self.error.clone(),
        }
    }

    pub fn create_pairing_code(&self, lifetime_secs: u64) -> String {
        let mut pairing = self.pairing.lock().expect("pairing lock");
        pairing.create_code(lifetime_secs)
    }

    pub fn is_running(&self) -> bool {
        self.join.is_some() && self.error.is_none()
    }
}

