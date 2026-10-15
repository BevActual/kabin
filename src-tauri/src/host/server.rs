use std::io::SeekFrom;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use axum::body::Body;
use axum::extract::{Query, State};
use axum::http::{header, HeaderMap, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use hyper_util::rt::TokioExecutor;
use hyper_util::server::conn::auto::Builder;
use hyper_util::service::TowerToHyperService;
use serde::Deserialize;
use serde_json::{json, Value};
use tokio::io::{AsyncReadExt, AsyncSeekExt};
use tokio::net::TcpListener;
use tokio_rustls::TlsAcceptor;

use super::catalog::{
    catalog_counts, media_file_for_item, progress_for, public_progress, serialize_item,
    tracks_progress,
};
use super::cert::{ensure_host_certificate, load_rustls_config};
use super::pairing::{PairingOutcome, PairingState};
use super::sessions::SessionStore;
use crate::config::{AppState, KabinConfig};
use crate::media_helper;

const MAX_PAYLOAD_BYTES: usize = 65536;

#[derive(Clone)]
struct ServerState {
    app: AppState,
    pairing: Arc<Mutex<PairingState>>,
    sessions: Arc<SessionStore>,
    host_name: String,
}

#[derive(Debug, Deserialize)]
struct ArtworkQuery {
    id: Option<String>,
}

#[derive(Debug, Deserialize)]
struct StreamQuery {
    id: Option<String>,
    track: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ProgressQuery {
    id: Option<String>,
}

pub async fn run(
    app: AppState,
    pairing: Arc<Mutex<PairingState>>,
    port: u16,
    host_name: String,
    mut shutdown: tokio::sync::oneshot::Receiver<()>,
) -> Result<(), String> {
    let (cert_path, key_path, _) = ensure_host_certificate()?;
    let rustls = Arc::new(load_rustls_config(&cert_path, &key_path)?);
    let acceptor = TlsAcceptor::from(rustls);

    let state = ServerState {
        app,
        pairing,
        sessions: Arc::new(SessionStore::default()),
        host_name,
    };
    let router = build_router(state);

    let listener = TcpListener::bind(format!("0.0.0.0:{port}"))
        .await
        .map_err(|e| e.to_string())?;

    loop {
        tokio::select! {
            _ = &mut shutdown => break,
            accept = listener.accept() => {
                let Ok((stream, _)) = accept else { continue };
                let acceptor = acceptor.clone();
                let router = router.clone();
                tokio::spawn(async move {
                    let Ok(tls) = acceptor.accept(stream).await else { return };
                    let io = hyper_util::rt::TokioIo::new(tls);
                    let service = TowerToHyperService::new(router);
                    if Builder::new(TokioExecutor::new())
                        .serve_connection(io, service)
                        .await
                        .is_err()
                    {
                        // client disconnected
                    }
                });
            }
        }
    }
    Ok(())
}

fn build_router(state: ServerState) -> Router {
    Router::new()
        .route("/v1/info", get(info_handler))
        .route("/v1/pair", post(pair_handler))
        .route("/v1/library", get(library_handler))
        .route("/v1/media/progress", get(get_progress_handler).post(post_progress_handler))
        .route("/v1/media/stream", get(stream_handler))
        .route("/v1/artwork", get(artwork_handler))
        .route("/v1/sessions", post(create_session_handler))
        .route("/v1/sessions/{session_id}", get(get_session_handler))
        .route("/v1/sessions/{session_id}/signal", post(signal_session_handler))
        .route("/v1/sessions/{session_id}/launch", post(launch_session_handler))
        .with_state(state)
}

async fn info_handler(State(state): State<ServerState>) -> impl IntoResponse {
    let ready = media_helper::self_test().unwrap_or(false);
    Json(json!({
        "protocol": 1,
        "name": state.host_name,
        "service": "Kabin Host",
        "pairing_required": true,
        "streaming": if ready { "kabin" } else { "none" },
        "media_ready": ready,
    }))
}

async fn create_session_handler(
    State(state): State<ServerState>,
    headers: HeaderMap,
    body: axum::body::Bytes,
) -> impl IntoResponse {
    if !authorized(&headers) {
        return json_error(StatusCode::UNAUTHORIZED, "authentication required");
    }
    let payload = match read_json_payload(&headers, &body) {
        Ok(v) => v,
        Err(resp) => return resp,
    };
    let game_id = payload
        .get("game_id")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .trim();
    if game_id.is_empty() {
        return json_error(StatusCode::BAD_REQUEST, "game_id is required");
    }
    let Some(item) = state.app.find_item(game_id) else {
        return json_error(StatusCode::NOT_FOUND, "game not found or not launchable");
    };
    let Some(session) = state.sessions.prepare(&item) else {
        return json_error(StatusCode::NOT_FOUND, "game not found or not launchable");
    };
    (StatusCode::CREATED, Json(session)).into_response()
}

async fn get_session_handler(
    State(state): State<ServerState>,
    headers: HeaderMap,
    axum::extract::Path(session_id): axum::extract::Path<String>,
) -> impl IntoResponse {
    if !authorized(&headers) {
        return json_error(StatusCode::UNAUTHORIZED, "authentication required");
    }
    match state.sessions.get(&session_id) {
        Some(session) => Json(session).into_response(),
        None => json_error(StatusCode::NOT_FOUND, "session not found"),
    }
}

async fn signal_session_handler(
    State(state): State<ServerState>,
    headers: HeaderMap,
    axum::extract::Path(session_id): axum::extract::Path<String>,
    body: axum::body::Bytes,
) -> impl IntoResponse {
    if !authorized(&headers) {
        return json_error(StatusCode::UNAUTHORIZED, "authentication required");
    }
    let payload = match read_json_payload(&headers, &body) {
        Ok(v) => v,
        Err(resp) => return resp,
    };
    if payload.get("type").and_then(|v| v.as_str()) != Some("offer") {
        return json_error(StatusCode::BAD_REQUEST, "offer sdp is required");
    }
    let Some(sdp) = payload.get("sdp").and_then(|v| v.as_str()) else {
        return json_error(StatusCode::BAD_REQUEST, "offer sdp is required");
    };
    let sessions = state.sessions.clone();
    let session_id_copy = session_id.clone();
    let sdp_owned = sdp.to_string();
    let answer = match tokio::task::spawn_blocking(move || {
        sessions.negotiate(&session_id_copy, &sdp_owned)
    })
    .await
    {
        Ok(Ok(answer)) => answer,
        Ok(Err(err)) => return json_error(StatusCode::SERVICE_UNAVAILABLE, &err),
        Err(_) => return json_error(StatusCode::INTERNAL_SERVER_ERROR, "negotiation failed"),
    };
    Json(json!({ "type": "answer", "sdp": answer })).into_response()
}

async fn launch_session_handler(
    State(state): State<ServerState>,
    headers: HeaderMap,
    axum::extract::Path(session_id): axum::extract::Path<String>,
) -> impl IntoResponse {
    if !authorized(&headers) {
        return json_error(StatusCode::UNAUTHORIZED, "authentication required");
    }
    let app = state.app.clone();
    let sessions = state.sessions.clone();
    match tokio::task::spawn_blocking(move || sessions.activate(&session_id, &app)).await {
        Ok(Ok(session)) => Json(session).into_response(),
        Ok(Err(err)) if err.contains("not connected") => {
            json_error(StatusCode::CONFLICT, &err)
        }
        Ok(Err(err)) if err.contains("not found") => json_error(StatusCode::NOT_FOUND, &err),
        Ok(Err(err)) => json_error(StatusCode::INTERNAL_SERVER_ERROR, &err),
        Err(_) => json_error(StatusCode::INTERNAL_SERVER_ERROR, "launch failed"),
    }
}

async fn pair_handler(
    State(state): State<ServerState>,
    headers: HeaderMap,
    body: axum::body::Bytes,
) -> impl IntoResponse {
    let payload = match read_json_payload(&headers, &body) {
        Ok(v) => v,
        Err(resp) => return resp,
    };
    let code = payload
        .get("code")
        .map(|v| match v {
            Value::String(s) => s.clone(),
            other => other.to_string(),
        })
        .unwrap_or_default();
    let outcome = {
        let mut pairing = state.pairing.lock().expect("pairing lock");
        pairing.attempt(&code)
    };
    match outcome {
        PairingOutcome::Locked => {
            json_error(StatusCode::TOO_MANY_REQUESTS, "too many pairing attempts")
        }
        PairingOutcome::Invalid => {
            json_error(StatusCode::FORBIDDEN, "invalid or expired pairing code")
        }
        PairingOutcome::Ok => {
            let device_name = payload
                .get("device_name")
                .and_then(|v| v.as_str())
                .unwrap_or("Kabin device");
            let device_name = device_name.chars().take(80).collect::<String>();
            let mut config = KabinConfig::load();
            let token = config.add_paired_device(&device_name);
            match config.save() {
                Ok(()) => (
                    StatusCode::CREATED,
                    Json(json!({
                        "token": token,
                        "host": state.host_name,
                    })),
                )
                    .into_response(),
                Err(err) => json_error(StatusCode::INTERNAL_SERVER_ERROR, &err),
            }
        }
    }
}

async fn library_handler(
    State(state): State<ServerState>,
    headers: HeaderMap,
) -> impl IntoResponse {
    if !authorized(&headers) {
        return json_error(StatusCode::UNAUTHORIZED, "authentication required");
    }
    let config = KabinConfig::load();
    let snapshot = state.app.snapshot(false);
    let items: Vec<Value> = snapshot
        .titles
        .iter()
        .filter_map(|title| state.app.find_item(&title.id))
        .map(|item| {
            serialize_item(
                &item,
                &config,
                tracks_progress(&item),
            )
        })
        .collect();
    let games: Vec<Value> = items
        .iter()
        .filter(|item| item.get("media_type").and_then(|v| v.as_str()) == Some("game"))
        .cloned()
        .collect();
    let counts = catalog_counts(&items);
    Json(json!({
        "items": items,
        "games": games,
        "count": items.len(),
        "counts": counts,
    }))
    .into_response()
}

async fn get_progress_handler(
    State(state): State<ServerState>,
    headers: HeaderMap,
    Query(query): Query<ProgressQuery>,
) -> impl IntoResponse {
    if !authorized(&headers) {
        return json_error(StatusCode::UNAUTHORIZED, "authentication required");
    }
    let config = KabinConfig::load();
    if let Some(item_id) = query.id.filter(|id| !id.is_empty()) {
        let mut body = progress_for(&config, &item_id);
        if let Some(obj) = body.as_object_mut() {
            obj.insert("id".to_string(), json!(item_id));
        }
        return Json(body).into_response();
    }
    let snapshot = state.app.snapshot(false);
    let mut payload = serde_json::Map::new();
    for title in snapshot.titles {
        let progress = progress_for(&config, &title.id);
        if progress
            .get("updated_at")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0)
            > 0.0
        {
            payload.insert(title.id, public_progress(&progress));
        }
    }
    Json(json!({ "progress": payload })).into_response()
}

async fn post_progress_handler(
    State(state): State<ServerState>,
    headers: HeaderMap,
    body: axum::body::Bytes,
) -> impl IntoResponse {
    if !authorized(&headers) {
        return json_error(StatusCode::UNAUTHORIZED, "authentication required");
    }
    let payload = match read_json_payload(&headers, &body) {
        Ok(v) => v,
        Err(resp) => return resp,
    };
    let item_id = payload.get("id").and_then(|v| v.as_str()).unwrap_or("");
    let Some(item) = state.app.find_item(item_id) else {
        return json_error(StatusCode::NOT_FOUND, "media not found");
    };
    if !tracks_progress(&item) {
        return json_error(StatusCode::NOT_FOUND, "media not found");
    }
    let position = payload.get("position").and_then(|v| v.as_f64()).unwrap_or(0.0);
    let duration = payload.get("duration").and_then(|v| v.as_f64()).unwrap_or(0.0);
    let track = payload
        .get("track")
        .and_then(|v| v.as_u64())
        .unwrap_or(0) as u32;
    let mut config = KabinConfig::load();
    if let Err(err) = config.save_progress(&item.id, position, duration, track) {
        return json_error(StatusCode::INTERNAL_SERVER_ERROR, &err);
    }
    state.app.invalidate();
    let mut body = progress_for(&config, &item.id);
    if let Some(obj) = body.as_object_mut() {
        obj.insert("id".to_string(), json!(item.id));
    }
    Json(body).into_response()
}

async fn artwork_handler(
    State(state): State<ServerState>,
    headers: HeaderMap,
    Query(query): Query<ArtworkQuery>,
) -> impl IntoResponse {
    if !authorized(&headers) {
        return json_error(StatusCode::UNAUTHORIZED, "authentication required");
    }
    let item_id = query.id.unwrap_or_default();
    if item_id.is_empty() {
        return json_error(StatusCode::NOT_FOUND, "artwork not found");
    }
    super::artwork::artwork_response(&state.app, &item_id).await
}

async fn stream_handler(
    State(state): State<ServerState>,
    headers: HeaderMap,
    Query(query): Query<StreamQuery>,
) -> impl IntoResponse {
    if !authorized(&headers) {
        return json_error(StatusCode::UNAUTHORIZED, "authentication required");
    }
    let item_id = query.id.unwrap_or_default();
    let track: usize = query
        .track
        .as_deref()
        .unwrap_or("0")
        .parse()
        .unwrap_or(0);
    let Some(item) = state.app.find_item(&item_id) else {
        return json_error(StatusCode::NOT_FOUND, "media not found");
    };
    let config = KabinConfig::load();
    let Some(path) = media_file_for_item(&item, &config, track) else {
        return json_error(StatusCode::NOT_FOUND, "media not found");
    };
    stream_file(&headers, path).await
}

async fn stream_file(headers: &HeaderMap, path: PathBuf) -> Response {
    let Ok(meta) = tokio::fs::metadata(&path).await else {
        return json_error(StatusCode::NOT_FOUND, "media not found");
    };
    let size = meta.len();
    let range_header = headers
        .get(header::RANGE)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    let (kind, start, end) = parse_byte_range(range_header, size);
    if kind == "unsatisfiable" {
        return Response::builder()
            .status(StatusCode::RANGE_NOT_SATISFIABLE)
            .header(header::CONTENT_RANGE, format!("bytes */{size}"))
            .header(header::CONTENT_LENGTH, "0")
            .body(Body::empty())
            .unwrap();
    }
    let length = end.saturating_sub(start).saturating_add(1);
    let status = if kind == "partial" {
        StatusCode::PARTIAL_CONTENT
    } else {
        StatusCode::OK
    };
    let mut file = match tokio::fs::File::open(&path).await {
        Ok(f) => f,
        Err(_) => return json_error(StatusCode::NOT_FOUND, "media not found"),
    };
    if start > 0 {
        if file.seek(SeekFrom::Start(start)).await.is_err() {
            return json_error(StatusCode::NOT_FOUND, "media not found");
        }
    }
    let mut buffer = vec![0u8; length as usize];
    if file.read_exact(&mut buffer).await.is_err() {
        return json_error(StatusCode::NOT_FOUND, "media not found");
    }
    let mut builder = Response::builder()
        .status(status)
        .header(header::CONTENT_TYPE, "application/octet-stream")
        .header(header::CONTENT_LENGTH, length.to_string())
        .header(header::ACCEPT_RANGES, "bytes")
        .header(header::CACHE_CONTROL, "private, no-transform");
    if status == StatusCode::PARTIAL_CONTENT {
        builder = builder.header(header::CONTENT_RANGE, format!("bytes {start}-{end}/{size}"));
    }
    builder.body(Body::from(buffer)).unwrap()
}

fn authorized(headers: &HeaderMap) -> bool {
    let token = headers
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .strip_prefix("Bearer ")
        .unwrap_or("");
    KabinConfig::load().network_token_valid(token)
}

fn read_json_payload(headers: &HeaderMap, body: &axum::body::Bytes) -> Result<Value, Response> {
    let length = headers
        .get(header::CONTENT_LENGTH)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("0")
        .parse::<isize>()
        .unwrap_or(0);
    if length < 0 {
        return Err(json_error(StatusCode::BAD_REQUEST, "invalid request"));
    }
    let capped = (length as usize).min(MAX_PAYLOAD_BYTES);
    if body.len() > capped.saturating_add(1024) {
        return Err(json_error(StatusCode::BAD_REQUEST, "invalid request"));
    }
    serde_json::from_slice(body).map_err(|_| json_error(StatusCode::BAD_REQUEST, "invalid request"))
}

fn json_error(status: StatusCode, message: &str) -> Response {
    let body = json!({ "error": message }).to_string();
    Response::builder()
        .status(status)
        .header(header::CONTENT_TYPE, "application/json")
        .header(header::CACHE_CONTROL, "no-store")
        .body(Body::from(body))
        .unwrap()
}

pub(crate) fn parse_byte_range(range_header: &str, size: u64) -> (&'static str, u64, u64) {
    let full = ("full", 0, size.saturating_sub(1));
    if size == 0 || !range_header.starts_with("bytes=") {
        return full;
    }
    let spec = range_header.trim_start_matches("bytes=").trim();
    if spec.contains(',') {
        return full;
    }
    let Some((start_text, end_text)) = spec.split_once('-') else {
        return full;
    };
    let parsed = if start_text.is_empty() {
        let Ok(suffix) = end_text.parse::<u64>() else {
            return full;
        };
        if suffix == 0 {
            return full;
        }
        let start = size.saturating_sub(suffix);
        ("partial", start, size - 1)
    } else {
        let Ok(start) = start_text.parse::<u64>() else {
            return full;
        };
        let end = if end_text.is_empty() {
            size - 1
        } else {
            match end_text.parse::<u64>() {
                Ok(v) => v,
                Err(_) => return full,
            }
        };
        if start >= size {
            return ("unsatisfiable", 0, 0);
        }
        let end = end.min(size - 1);
        if end < start {
            return ("unsatisfiable", 0, 0);
        }
        ("partial", start, end)
    };
    parsed
}

#[cfg(test)]
mod tests {
    use super::parse_byte_range;

    #[test]
    fn suffix_range_reads_tail_bytes() {
        let (kind, start, end) = parse_byte_range("bytes=-5", 100);
        assert_eq!(kind, "partial");
        assert_eq!(start, 95);
        assert_eq!(end, 99);
    }
}
