use std::path::PathBuf;
use std::sync::Arc;

use librqbit::api::TorrentIdOrHash;
use librqbit::{AddTorrent, AddTorrentOptions, Session, SessionOptions, TorrentStatsState};

pub async fn open_session(download_dir: PathBuf) -> Result<Arc<Session>, String> {
    std::fs::create_dir_all(&download_dir).map_err(|error| error.to_string())?;
    let mut options = SessionOptions::default();
    options.client_name_and_version = Some("Kabin/0.1".into());
    options.fastresume = true;
    match Session::new_with_opts(download_dir.clone(), options).await {
        Ok(session) => Ok(session),
        Err(error) => {
            let mut options = SessionOptions::default();
            options.client_name_and_version = Some("Kabin/0.1".into());
            options.fastresume = true;
            options.ipv4_only = true;
            Session::new_with_opts(download_dir, options)
                .await
                .map_err(|_| format!("Could not start the torrent client: {error}"))
        }
    }
}

pub async fn add_torrent(
    session: &Arc<Session>,
    source: &str,
    output_folder: PathBuf,
) -> Result<usize, String> {
    std::fs::create_dir_all(&output_folder).map_err(|error| error.to_string())?;
    let add = if output_is_local_torrent(source) {
        let bytes = std::fs::read(source).map_err(|error| error.to_string())?;
        AddTorrent::TorrentFileBytes(bytes::Bytes::from(bytes))
    } else {
        AddTorrent::Url(std::borrow::Cow::Owned(source.to_string()))
    };
    let options = AddTorrentOptions {
        overwrite: true,
        output_folder: Some(output_folder.to_string_lossy().into_owned()),
        ..Default::default()
    };
    let response = session
        .add_torrent(add, Some(options))
        .await
        .map_err(|error| format!("Could not add torrent: {error}"))?;
    match response {
        librqbit::AddTorrentResponse::Added(id, _)
        | librqbit::AddTorrentResponse::AlreadyManaged(id, _) => Ok(id),
        librqbit::AddTorrentResponse::ListOnly(_) => Err("Torrent had no files to download".into()),
    }
}

pub async fn pause(session: &Session, id: usize) -> Result<(), String> {
    let handle = session
        .get(TorrentIdOrHash::Id(id))
        .ok_or_else(|| "That torrent is no longer running".to_string())?;
    session
        .pause(&handle)
        .await
        .map_err(|error| error.to_string())
}

pub async fn resume(session: &Arc<Session>, id: usize) -> Result<(), String> {
    let handle = session
        .get(TorrentIdOrHash::Id(id))
        .ok_or_else(|| "That torrent is no longer running".to_string())?;
    session
        .unpause(&handle)
        .await
        .map_err(|error| error.to_string())
}

pub async fn remove(session: &Session, id: usize) -> Result<(), String> {
    session
        .delete(TorrentIdOrHash::Id(id), false)
        .await
        .map_err(|error| error.to_string())
}

#[derive(Debug, Clone)]
pub struct TorrentProgress {
    pub name: Option<String>,
    pub status: String,
    pub progress: f32,
    pub bytes_done: u64,
    pub bytes_total: u64,
    pub error: String,
    pub output_path: String,
}

pub fn progress(session: &Session, id: usize) -> Option<TorrentProgress> {
    let handle = session.get(TorrentIdOrHash::Id(id))?;
    let stats = handle.stats();
    let progress = if stats.total_bytes == 0 {
        0.0
    } else {
        (stats.progress_bytes as f32 / stats.total_bytes as f32).clamp(0.0, 1.0)
    };
    let status = match stats.state {
        TorrentStatsState::Paused | TorrentStatsState::Initializing { paused: true } => "paused",
        TorrentStatsState::Error => "error",
        TorrentStatsState::Live | TorrentStatsState::Initializing { paused: false }
            if stats.finished =>
        {
            "complete"
        }
        TorrentStatsState::Live | TorrentStatsState::Initializing { paused: false } => {
            "downloading"
        }
    };
    Some(TorrentProgress {
        name: handle.name().map(|name| name.to_string()),
        status: status.to_string(),
        progress: if stats.finished { 1.0 } else { progress },
        bytes_done: stats.progress_bytes,
        bytes_total: stats.total_bytes,
        error: stats.error.unwrap_or_default(),
        output_path: handle.output_folder().to_string_lossy().into_owned(),
    })
}

fn output_is_local_torrent(source: &str) -> bool {
    !source.contains("://") && std::path::Path::new(source).is_file()
}
