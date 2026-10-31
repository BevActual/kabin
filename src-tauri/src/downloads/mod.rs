mod import;
mod indexers;
mod nntp;
mod nzb;
mod settings;
mod torrent;
mod usenet;
mod yenc;

use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use serde::Serialize;

use import::import_videos;
use indexers::search_indexers;
pub use indexers::ReleaseHit;
pub use settings::{Indexer, UsenetServer, WantedItem};

use settings::{
    DownloadSettings, ensure_dir, jobs_path, kabin_download_root, load, new_id, sanitize_name,
    save,
};

#[derive(Clone)]
pub struct DownloadEngine {
    inner: Arc<Inner>,
}

struct Inner {
    jobs: Mutex<Vec<JobRecord>>,
    cancels: Mutex<std::collections::HashMap<String, Arc<AtomicBool>>>,
    session: tokio::sync::Mutex<Option<Arc<librqbit::Session>>>,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct JobRecord {
    id: String,
    name: String,
    protocol: String,
    source: String,
    status: String,
    #[serde(default)]
    error: String,
    #[serde(default)]
    progress: f32,
    #[serde(default)]
    bytes_done: u64,
    #[serde(default)]
    bytes_total: u64,
    #[serde(default)]
    output_path: String,
    #[serde(default)]
    torrent_id: Option<usize>,
    #[serde(default)]
    wanted_id: String,
    #[serde(default)]
    imported: bool,
    #[serde(default)]
    import_checked: bool,
    #[serde(default)]
    nzb_path: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct JobView {
    pub id: String,
    pub name: String,
    pub protocol: String,
    pub status: String,
    pub error: String,
    pub progress: f32,
    pub bytes_done: u64,
    pub bytes_total: u64,
    pub output_path: String,
    pub imported: bool,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct IndexerView {
    pub id: String,
    pub name: String,
    pub url: String,
    pub kind: String,
    pub has_api_key: bool,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UsenetView {
    pub host: String,
    pub port: u16,
    pub ssl: bool,
    pub username: String,
    pub has_password: bool,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DownloadStatus {
    pub quality: String,
    pub import_dir: String,
    pub download_dir: String,
    pub connections: u16,
    pub usenet: UsenetView,
    pub indexers: Vec<IndexerView>,
    pub wanted: Vec<WantedItem>,
    pub jobs: Vec<JobView>,
}

impl DownloadEngine {
    pub fn new() -> Self {
        Self {
            inner: Arc::new(Inner {
                jobs: Mutex::new(load_jobs()),
                cancels: Mutex::new(std::collections::HashMap::new()),
                session: tokio::sync::Mutex::new(None),
            }),
        }
    }

    pub async fn resume(self) {
        let pending: Vec<JobRecord> = self
            .inner
            .jobs
            .lock()
            .expect("jobs")
            .iter()
            .filter(|job| job.status == "downloading" || job.status == "queued")
            .cloned()
            .collect();
        for job in pending {
            if job.protocol == "torrent" {
                if let Err(error) = self.start_torrent(&job).await {
                    self.fail_job(&job.id, &error);
                }
            } else if let Err(error) = self.start_usenet(&job).await {
                self.fail_job(&job.id, &error);
            }
        }
    }

    pub async fn status(&self) -> DownloadStatus {
        self.refresh_torrents().await;
        let settings = load();
        let jobs = self
            .inner
            .jobs
            .lock()
            .expect("jobs")
            .iter()
            .map(JobRecord::view)
            .collect();
        let download_dir = displayed_download_dir(&settings);
        let usenet = UsenetView {
            host: settings.usenet.host.clone(),
            port: settings.usenet.resolved_port(),
            ssl: settings.usenet.ssl,
            username: settings.usenet.username.clone(),
            has_password: !settings.usenet.password.is_empty(),
        };
        let indexers = settings
            .indexers
            .iter()
            .map(|indexer| IndexerView {
                id: indexer.id.clone(),
                name: indexer.name.clone(),
                url: indexer.url.clone(),
                kind: indexer.kind.clone(),
                has_api_key: !indexer.api_key.is_empty(),
            })
            .collect();
        DownloadStatus {
            quality: settings.quality,
            import_dir: settings.import_dir,
            download_dir,
            connections: settings.connections.clamp(1, 20),
            usenet,
            indexers,
            wanted: settings.wanted,
            jobs,
        }
    }

    pub fn set_quality(&self, quality: String) -> Result<(), String> {
        let mut settings = load();
        settings.quality = normalize_quality(&quality);
        save(&settings)
    }

    pub fn set_import_dir(&self, path: String) -> Result<(), String> {
        let mut settings = load();
        settings.import_dir = path.trim().to_string();
        save(&settings)
    }

    pub fn set_download_dir(&self, path: String) -> Result<(), String> {
        let mut settings = load();
        settings.download_dir = path.trim().to_string();
        save(&settings)
    }

    pub fn set_connections(&self, connections: u16) -> Result<(), String> {
        let mut settings = load();
        settings.connections = connections.clamp(1, 20);
        save(&settings)
    }

    pub fn save_usenet(&self, incoming: UsenetServer) -> Result<(), String> {
        let mut settings = load();
        let mut server = incoming;
        if server.password.is_empty() {
            server.password = settings.usenet.password.clone();
        }
        if server.port == 0 {
            server.port = server.resolved_port();
        }
        settings.usenet = server;
        save(&settings)
    }

    pub async fn test_usenet(&self) -> Result<String, String> {
        let settings = load();
        let host = settings.usenet.host.trim().to_string();
        let mut conn = nntp::NntpConn::connect(&settings.usenet).await?;
        let _ = conn.command("QUIT").await;
        Ok(format!("Connected to {host}"))
    }

    pub fn upsert_indexer(&self, indexer: Indexer) -> Result<(), String> {
        let name = indexer.name.trim().to_string();
        if name.is_empty() {
            return Err("Name the indexer".into());
        }
        if !(indexer.url.starts_with("http://") || indexer.url.starts_with("https://")) {
            return Err("Indexer address must start with http:// or https://".into());
        }
        let kind = if indexer.kind == "newznab" {
            "newznab"
        } else {
            "torznab"
        };
        let mut settings = load();
        let mut stored = indexer;
        stored.name = name;
        stored.kind = kind.to_string();
        let existing_key = settings
            .indexers
            .iter()
            .find(|item| item.id == stored.id)
            .map(|item| item.api_key.clone());
        if let Some(key) = existing_key {
            if stored.api_key.is_empty() {
                stored.api_key = key;
            }
            let id = stored.id.clone();
            if let Some(slot) = settings.indexers.iter_mut().find(|item| item.id == id) {
                *slot = stored;
            }
        } else {
            if stored.id.is_empty() {
                stored.id = new_id();
            }
            settings.indexers.push(stored);
        }
        save(&settings)
    }

    pub fn remove_indexer(&self, id: &str) -> Result<(), String> {
        let mut settings = load();
        settings.indexers.retain(|indexer| indexer.id != id);
        save(&settings)
    }

    pub fn add_wanted(&self, title: String, year: String, kind: String) -> Result<WantedItem, String> {
        let title = title.trim();
        if title.is_empty() {
            return Err("Enter a title".into());
        }
        let settings_now = load();
        let item = WantedItem {
            id: new_id(),
            title: title.to_string(),
            year: year.trim().to_string(),
            kind: if kind == "series" { "series" } else { "movie" }.to_string(),
            quality: settings_now.quality.clone(),
        };
        let mut settings = settings_now;
        settings.wanted.insert(0, item.clone());
        save(&settings)?;
        Ok(item)
    }

    pub fn remove_wanted(&self, id: &str) -> Result<(), String> {
        let mut settings = load();
        settings.wanted.retain(|item| item.id != id);
        save(&settings)
    }

    pub async fn search_wanted(&self, id: &str) -> Result<Vec<ReleaseHit>, String> {
        let settings = load();
        let wanted = settings
            .wanted
            .iter()
            .find(|item| item.id == id)
            .cloned()
            .ok_or_else(|| "That title is no longer in Wanted".to_string())?;
        let query = format!("{} {}", wanted.title, wanted.year);
        let indexers = settings.indexers.clone();
        let quality = wanted.quality.clone();
        tokio::task::spawn_blocking(move || search_indexers(&indexers, &query, &quality))
            .await
            .map_err(|error| error.to_string())?
    }

    pub async fn add_download(
        &self,
        link: String,
        name: String,
        protocol: String,
        wanted_id: String,
    ) -> Result<String, String> {
        let link = link.trim().to_string();
        if link.is_empty() {
            return Err("Add a magnet link or an NZB address".into());
        }
        let protocol = detect_protocol(&link, &protocol);
        let name = if name.trim().is_empty() {
            "Download".into()
        } else {
            name.trim().to_string()
        };
        let id = new_id();
        let output = kabin_download_root().join(format!("{}-{id}", sanitize_name(&name)));
        ensure_dir(&output)?;
        let job = JobRecord {
            id: id.clone(),
            name,
            protocol: protocol.clone(),
            source: link,
            status: "queued".into(),
            error: String::new(),
            progress: 0.0,
            bytes_done: 0,
            bytes_total: 0,
            output_path: output.to_string_lossy().into_owned(),
            torrent_id: None,
            wanted_id,
            imported: false,
            import_checked: false,
            nzb_path: String::new(),
        };
        {
            let mut jobs = self.inner.jobs.lock().expect("jobs");
            jobs.insert(0, job.clone());
            persist_jobs(&jobs)?;
        }
        if protocol == "torrent" {
            self.start_torrent(&job).await.map_err(|error| {
                self.fail_job(&id, &error);
                error
            })?;
        } else {
            self.start_usenet(&job).await.map_err(|error| {
                self.fail_job(&id, &error);
                error
            })?;
        }
        Ok(id)
    }

    pub async fn download_action(&self, id: String, action: String) -> Result<(), String> {
        let job = self
            .inner
            .jobs
            .lock()
            .expect("jobs")
            .iter()
            .find(|job| job.id == id)
            .cloned()
            .ok_or_else(|| "That download is no longer in the queue".to_string())?;
        match action.as_str() {
            "pause" => self.pause_job(&job).await,
            "resume" => self.resume_job(&job).await,
            "remove" => self.remove_job(&job).await,
            _ => Err("Unknown download action".into()),
        }
    }

    async fn start_torrent(&self, job: &JobRecord) -> Result<(), String> {
        let session = self.ensure_session().await?;
        let torrent_id =
            torrent::add_torrent(&session, &job.source, PathBuf::from(&job.output_path)).await?;
        let mut jobs = self.inner.jobs.lock().expect("jobs");
        if let Some(slot) = jobs.iter_mut().find(|item| item.id == job.id) {
            slot.torrent_id = Some(torrent_id);
            slot.status = "downloading".into();
            slot.error.clear();
        }
        persist_jobs(&jobs)
    }

    async fn start_usenet(&self, job: &JobRecord) -> Result<(), String> {
        let settings = load();
        if settings.usenet.host.trim().is_empty() {
            return Err("Add a Usenet server in Settings".into());
        }
        let nzb_path = if job.nzb_path.is_empty() {
            let bytes = load_nzb_source(&job.source)?;
            let dir = jobs_path()
                .parent()
                .unwrap_or_else(|| Path::new("."))
                .join("nzb");
            ensure_dir(&dir)?;
            let path = dir.join(format!("{}.nzb", job.id));
            fs::write(&path, &bytes).map_err(|error| error.to_string())?;
            path
        } else {
            PathBuf::from(&job.nzb_path)
        };
        let bytes = fs::read(&nzb_path).map_err(|error| format!("Could not read NZB: {error}"))?;
        let files = usenet::read_nzb_bytes(&bytes)?;
        let output = PathBuf::from(&job.output_path);
        let cancel = Arc::new(AtomicBool::new(false));
        self.inner
            .cancels
            .lock()
            .expect("cancels")
            .insert(job.id.clone(), cancel.clone());
        {
            let mut jobs = self.inner.jobs.lock().expect("jobs");
            if let Some(slot) = jobs.iter_mut().find(|item| item.id == job.id) {
                slot.nzb_path = nzb_path.to_string_lossy().into_owned();
                slot.status = "downloading".into();
                slot.error.clear();
                slot.bytes_total = files.iter().map(|file| file.segments.len() as u64).sum();
            }
            persist_jobs(&jobs)?;
        }
        let engine = self.clone();
        let job_id = job.id.clone();
        let connections = settings.connections.clamp(1, 20) as usize;
        let on_progress: Arc<dyn Fn(u64, u64) + Send + Sync> = Arc::new(move |done, total| {
            engine.set_progress(&job_id, done, total);
        });
        let job_id = job.id.clone();
        let engine = self.clone();
        tokio::spawn(async move {
            let result = usenet::download_nzb(
                settings.usenet,
                files,
                output,
                connections,
                cancel,
                on_progress,
            )
            .await;
            engine.finish_usenet(&job_id, result);
        });
        Ok(())
    }

    async fn ensure_session(&self) -> Result<Arc<librqbit::Session>, String> {
        let mut slot = self.inner.session.lock().await;
        if let Some(session) = slot.as_ref() {
            return Ok(session.clone());
        }
        let session = torrent::open_session(kabin_download_root()).await?;
        *slot = Some(session.clone());
        Ok(session)
    }

    async fn refresh_torrents(&self) {
        let session = {
            let slot = self.inner.session.lock().await;
            slot.clone()
        };
        let Some(session) = session else {
            return;
        };
        let mut imports = Vec::new();
        {
            let mut jobs = self.inner.jobs.lock().expect("jobs");
            for job in jobs.iter_mut().filter(|job| job.protocol == "torrent") {
                let Some(id) = job.torrent_id else {
                    continue;
                };
                let Some(progress) = torrent::progress(&session, id) else {
                    continue;
                };
                job.progress = progress.progress;
                job.bytes_done = progress.bytes_done;
                job.bytes_total = progress.bytes_total;
                if !progress.output_path.is_empty() {
                    job.output_path = progress.output_path;
                }
                if job.name == "Download" {
                    if let Some(name) = progress.name {
                        job.name = name;
                    }
                }
                if job.status != "paused" {
                    job.status = progress.status;
                    job.error = progress.error;
                }
                if job.status == "complete" && !job.imported && !job.import_checked {
                    imports.push(job.clone());
                }
            }
        }
        for job in imports {
            self.import_job(&job);
        }
    }

    fn set_progress(&self, id: &str, done: u64, total: u64) {
        let mut jobs = self.inner.jobs.lock().expect("jobs");
        if let Some(job) = jobs.iter_mut().find(|job| job.id == id) {
            if job.status == "paused" || job.status == "error" {
                return;
            }
            job.bytes_done = done;
            job.bytes_total = total;
            job.progress = if total == 0 {
                0.0
            } else {
                (done as f32 / total as f32).clamp(0.0, 1.0)
            };
            job.status = "downloading".into();
        }
    }

    fn finish_usenet(&self, id: &str, result: Result<(), String>) {
        let job = {
            let mut jobs = self.inner.jobs.lock().expect("jobs");
            let Some(job) = jobs.iter_mut().find(|job| job.id == id) else {
                return;
            };
            match result {
                Ok(()) => {
                    job.status = "complete".into();
                    job.progress = 1.0;
                    job.error.clear();
                }
                Err(error) if error == "paused" => {
                    job.status = "paused".into();
                }
                Err(error) => {
                    job.status = "error".into();
                    job.error = error;
                }
            }
            let snapshot = job.clone();
            let _ = persist_jobs(&jobs);
            snapshot
        };
        if job.status == "complete" {
            self.import_job(&job);
        }
    }

    fn import_job(&self, job: &JobRecord) {
        let settings = load();
        if settings.import_dir.trim().is_empty() {
            let mut jobs = self.inner.jobs.lock().expect("jobs");
            if let Some(slot) = jobs.iter_mut().find(|item| item.id == job.id) {
                if slot.error.is_empty() {
                    slot.error = "Download finished. Choose a library folder in Settings to add the video.".into();
                    let _ = persist_jobs(&jobs);
                }
            }
            return;
        }
        let imported = import_videos(Path::new(&job.output_path), Path::new(&settings.import_dir));
        let mut jobs = self.inner.jobs.lock().expect("jobs");
        if let Some(slot) = jobs.iter_mut().find(|item| item.id == job.id) {
            {
                slot.import_checked = true;
                match imported {
                    Ok(files) if !files.is_empty() => {
                        slot.imported = true;
                        slot.error.clear();
                    }
                    Ok(_) => {
                        slot.error =
                            "Download finished. No video file was ready to add to the library."
                                .into();
                    }
                    Err(error) => {
                        slot.error = error;
                    }
                }
            }
        }
        let _ = persist_jobs(&jobs);
    }

    fn fail_job(&self, id: &str, error: &str) {
        let mut jobs = self.inner.jobs.lock().expect("jobs");
        if let Some(job) = jobs.iter_mut().find(|job| job.id == id) {
            job.status = "error".into();
            job.error = error.to_string();
        }
        let _ = persist_jobs(&jobs);
    }

    async fn pause_job(&self, job: &JobRecord) -> Result<(), String> {
        if job.protocol == "torrent" {
            if let Some(id) = job.torrent_id {
                let session = self.ensure_session().await?;
                torrent::pause(&session, id).await?;
            }
        } else if let Some(flag) = self.inner.cancels.lock().expect("cancels").get(&job.id) {
            flag.store(true, Ordering::Relaxed);
        }
        let mut jobs = self.inner.jobs.lock().expect("jobs");
        if let Some(slot) = jobs.iter_mut().find(|item| item.id == job.id) {
            slot.status = "paused".into();
        }
        persist_jobs(&jobs)
    }

    async fn resume_job(&self, job: &JobRecord) -> Result<(), String> {
        if job.protocol == "torrent" {
            if let Some(id) = job.torrent_id {
                let session = self.ensure_session().await?;
                torrent::resume(&session, id).await?;
                let mut jobs = self.inner.jobs.lock().expect("jobs");
                if let Some(slot) = jobs.iter_mut().find(|item| item.id == job.id) {
                    slot.status = "downloading".into();
                    slot.error.clear();
                }
                return persist_jobs(&jobs);
            }
            return self.start_torrent(job).await;
        }
        self.start_usenet(job).await
    }

    async fn remove_job(&self, job: &JobRecord) -> Result<(), String> {
        if job.protocol == "torrent" {
            if let Some(id) = job.torrent_id {
                if let Some(session) = self.inner.session.lock().await.clone() {
                    let _ = torrent::remove(&session, id).await;
                }
            }
        } else if let Some(flag) = self.inner.cancels.lock().expect("cancels").remove(&job.id) {
            flag.store(true, Ordering::Relaxed);
        }
        let mut jobs = self.inner.jobs.lock().expect("jobs");
        jobs.retain(|item| item.id != job.id);
        persist_jobs(&jobs)
    }
}

impl Default for DownloadEngine {
    fn default() -> Self {
        Self::new()
    }
}

impl JobRecord {
    fn view(&self) -> JobView {
        JobView {
            id: self.id.clone(),
            name: self.name.clone(),
            protocol: self.protocol.clone(),
            status: self.status.clone(),
            error: self.error.clone(),
            progress: self.progress,
            bytes_done: self.bytes_done,
            bytes_total: self.bytes_total,
            output_path: self.output_path.clone(),
            imported: self.imported,
        }
    }
}

fn displayed_download_dir(settings: &DownloadSettings) -> String {
    if settings.download_dir.trim().is_empty() {
        kabin_download_root().to_string_lossy().into_owned()
    } else {
        settings.download_dir.clone()
    }
}

fn normalize_quality(quality: &str) -> String {
    match quality {
        "720p" | "1080p" | "2160p" | "any" => quality.to_string(),
        _ => "1080p".into(),
    }
}

fn detect_protocol(link: &str, hint: &str) -> String {
    if hint == "torrent" || hint == "usenet" {
        return hint.to_string();
    }
    let lower = link.to_ascii_lowercase();
    if lower.starts_with("magnet:")
        || lower.ends_with(".torrent")
        || lower.contains("xt=urn:btih")
    {
        "torrent".into()
    } else {
        "usenet".into()
    }
}

fn load_nzb_source(source: &str) -> Result<Vec<u8>, String> {
    let path = Path::new(source);
    if !source.contains("://") && path.is_file() {
        return fs::read(path).map_err(|error| error.to_string());
    }
    if !(source.starts_with("http://") || source.starts_with("https://")) {
        return Err("Usenet downloads need an NZB address or NZB file".into());
    }
    let response = ureq::get(source)
        .timeout(Duration::from_secs(60))
        .set("User-Agent", "Kabin")
        .call()
        .map_err(|error| format!("Could not download NZB: {error}"))?;
    let mut body = Vec::new();
    response
        .into_reader()
        .take(32_000_000)
        .read_to_end(&mut body)
        .map_err(|error| error.to_string())?;
    Ok(body)
}

fn load_jobs() -> Vec<JobRecord> {
    fs::read_to_string(jobs_path())
        .ok()
        .and_then(|raw| serde_json::from_str(&raw).ok())
        .unwrap_or_default()
}

fn persist_jobs(jobs: &[JobRecord]) -> Result<(), String> {
    let path = jobs_path();
    if let Some(parent) = path.parent() {
        ensure_dir(parent)?;
    }
    let payload = serde_json::to_string_pretty(jobs).map_err(|error| error.to_string())?;
    fs::write(path, payload).map_err(|error| error.to_string())
}
