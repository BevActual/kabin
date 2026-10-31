use std::collections::HashSet;
use std::fs::{self, OpenOptions};
use std::io::{Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use tokio::sync::mpsc;

use super::nntp::NntpConn;
use super::nzb::{NzbFile, parse_nzb};
use super::settings::UsenetServer;
use super::yenc::decode_yenc;

pub async fn download_nzb(
    server: UsenetServer,
    files: Vec<NzbFile>,
    dest: PathBuf,
    connections: usize,
    cancel: Arc<AtomicBool>,
    on_progress: Arc<dyn Fn(u64, u64) + Send + Sync>,
) -> Result<(), String> {
    fs::create_dir_all(&dest).map_err(|error| error.to_string())?;
    let done = Arc::new(Mutex::new(load_parts(&dest)));
    let total = files.iter().map(|file| file.segments.len() as u64).sum();
    let already = files
        .iter()
        .flat_map(|file| file.segments.iter().map(move |segment| part_key(&file.name, segment.number)))
        .filter(|key| done.lock().expect("parts").contains(key))
        .count() as u64;
    let completed = Arc::new(AtomicU64::new(already));
    on_progress(already, total);
    let (tx, rx) = mpsc::channel::<Work>(64);
    let rx = Arc::new(tokio::sync::Mutex::new(rx));
    let workers = connections.clamp(1, 20);
    let mut tasks = Vec::new();
    for _ in 0..workers {
        let server = server.clone();
        let dest = dest.clone();
        let cancel = cancel.clone();
        let done = done.clone();
        let completed = completed.clone();
        let on_progress = on_progress.clone();
        let rx = rx.clone();
        tasks.push(tokio::spawn(async move {
            worker(server, dest, cancel, done, completed, total, on_progress, rx).await
        }));
    }

    let mut queued = 0u64;
    for (file_index, file) in files.iter().enumerate() {
        for segment in &file.segments {
            let key = part_key(&file.name, segment.number);
            if done.lock().expect("parts").contains(&key) {
                continue;
            }
            tx.send(Work {
                file_index,
                number: segment.number,
                message_id: segment.message_id.clone(),
                groups: file.groups.clone(),
                fallback_name: file.name.clone(),
            })
            .await
            .map_err(|_| "Usenet download stopped".to_string())?;
            queued += 1;
        }
    }
    drop(tx);
    if queued == 0 && total > 0 {
        completed.store(total, Ordering::Relaxed);
    }

    let mut failures = Vec::new();
    for task in tasks {
        match task.await {
            Ok(Ok(())) => {}
            Ok(Err(error)) => failures.push(error),
            Err(error) => failures.push(error.to_string()),
        }
    }
    if cancel.load(Ordering::Relaxed) {
        return Err("paused".into());
    }
    if let Some(error) = failures.into_iter().next() {
        return Err(error);
    }
    Ok(())
}

struct Work {
    file_index: usize,
    number: u32,
    message_id: String,
    groups: Vec<String>,
    fallback_name: String,
}

async fn worker(
    server: UsenetServer,
    dest: PathBuf,
    cancel: Arc<AtomicBool>,
    done: Arc<Mutex<HashSet<String>>>,
    completed: Arc<AtomicU64>,
    total: u64,
    on_progress: Arc<dyn Fn(u64, u64) + Send + Sync>,
    rx: Arc<tokio::sync::Mutex<mpsc::Receiver<Work>>>,
) -> Result<(), String> {
    let mut conn: Option<NntpConn> = None;
    let mut joined = String::new();
    loop {
        if cancel.load(Ordering::Relaxed) {
            return Err("paused".into());
        }
        let work = {
            let mut rx = rx.lock().await;
            rx.recv().await
        };
        let Some(work) = work else {
            return Ok(());
        };
        let mut last_error = String::from("Could not download an article");
        let mut article = None;
        for _ in 0..3 {
            if cancel.load(Ordering::Relaxed) {
                return Err("paused".into());
            }
            if conn.is_none() {
                conn = Some(NntpConn::connect(&server).await?);
                joined.clear();
            }
            let connection = conn.as_mut().expect("connection");
            let group = work.groups.first().map(String::as_str).unwrap_or("");
            if !group.is_empty() && joined != group {
                let status = connection.command(&format!("GROUP {group}")).await?;
                if !status.starts_with("211") {
                    last_error = status;
                    conn = None;
                    continue;
                }
                joined = group.to_string();
            }
            match connection.body(&work.message_id).await {
                Ok(body) => {
                    article = Some(body);
                    break;
                }
                Err(error) => {
                    last_error = error;
                    conn = None;
                }
            }
        }
        let Some(article) = article else {
            return Err(last_error);
        };
        let part = decode_yenc(&article)?;
        let name = if part.name.trim().is_empty() {
            work.fallback_name.clone()
        } else {
            part.name.clone()
        };
        let filename = safe_filename(&name, work.file_index);
        write_part(&dest, &filename, part.begin, &part.data)?;
        let key = part_key(&work.fallback_name, work.number);
        {
            let mut done = done.lock().expect("parts");
            done.insert(key);
            save_parts(&dest, &done)?;
        }
        let done_count = completed.fetch_add(1, Ordering::Relaxed) + 1;
        on_progress(done_count, total);
    }
}

fn write_part(dest: &Path, filename: &str, begin: u64, data: &[u8]) -> Result<(), String> {
    let path = dest.join(filename);
    let mut file = OpenOptions::new()
        .create(true)
        .truncate(false)
        .write(true)
        .open(&path)
        .map_err(|error| format!("Could not write {filename}: {error}"))?;
    let offset = begin.saturating_sub(1);
    file.seek(SeekFrom::Start(offset))
        .map_err(|error| error.to_string())?;
    file.write_all(data).map_err(|error| error.to_string())?;
    Ok(())
}

fn safe_filename(name: &str, index: usize) -> String {
    let base = Path::new(name)
        .file_name()
        .and_then(|value| value.to_str())
        .unwrap_or("")
        .trim()
        .trim_start_matches('.');
    if base.is_empty() {
        format!("file-{index}")
    } else {
        base.to_string()
    }
}

fn part_key(name: &str, number: u32) -> String {
    format!("{name}\t{number}")
}

fn parts_path(dest: &Path) -> PathBuf {
    dest.join(".kabin-parts.json")
}

fn load_parts(dest: &Path) -> HashSet<String> {
    fs::read_to_string(parts_path(dest))
        .ok()
        .and_then(|raw| serde_json::from_str(&raw).ok())
        .unwrap_or_default()
}

fn save_parts(dest: &Path, parts: &HashSet<String>) -> Result<(), String> {
    let payload = serde_json::to_string(parts).map_err(|error| error.to_string())?;
    fs::write(parts_path(dest), payload).map_err(|error| error.to_string())
}

pub fn read_nzb_bytes(bytes: &[u8]) -> Result<Vec<NzbFile>, String> {
    let bytes = if bytes.starts_with(&[0x1f, 0x8b]) {
        let mut decoder = flate2::read::GzDecoder::new(bytes);
        let mut decoded = Vec::new();
        std::io::Read::read_to_end(&mut decoder, &mut decoded)
            .map_err(|error| format!("Could not decompress NZB: {error}"))?;
        decoded
    } else {
        bytes.to_vec()
    };
    let xml = String::from_utf8_lossy(&bytes);
    parse_nzb(&xml)
}
