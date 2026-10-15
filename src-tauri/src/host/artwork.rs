use std::path::Path;

use axum::body::Body;
use axum::http::{header, StatusCode};
use axum::response::Response;

use crate::catalog::artwork::{artwork_file_for_item, is_safe_artwork_file};
use crate::config::AppState;

pub async fn artwork_response(app: &AppState, item_id: &str) -> Response {
    let Some(item) = app.find_item(item_id) else {
        return json_error(StatusCode::NOT_FOUND, "artwork not found");
    };
    let Some(path) = artwork_file_for_item(&item) else {
        return json_error(StatusCode::NOT_FOUND, "artwork not found");
    };
    image_response(&path)
}

fn image_response(path: &Path) -> Response {
    if !is_safe_artwork_file(path) {
        return json_error(StatusCode::NOT_FOUND, "artwork not found");
    }
    let Ok(data) = std::fs::read(path) else {
        return json_error(StatusCode::NOT_FOUND, "artwork not found");
    };
    if data.is_empty() || data.len() > 15 * 1024 * 1024 {
        return json_error(StatusCode::NOT_FOUND, "artwork not found");
    }
    let content_type = if data.starts_with(b"\x89PNG\r\n\x1a\n") {
        "image/png"
    } else if data.starts_with(b"\xff\xd8\xff") {
        "image/jpeg"
    } else if data.starts_with(b"RIFF") && data.get(8..12) == Some(b"WEBP") {
        "image/webp"
    } else {
        return json_error(StatusCode::UNSUPPORTED_MEDIA_TYPE, "unsupported artwork");
    };
    Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, content_type)
        .header(header::CONTENT_LENGTH, data.len().to_string())
        .header(header::CACHE_CONTROL, "private, max-age=86400")
        .body(Body::from(data))
        .unwrap()
}

fn json_error(status: StatusCode, message: &str) -> Response {
    let body = serde_json::json!({ "error": message }).to_string();
    Response::builder()
        .status(status)
        .header(header::CONTENT_TYPE, "application/json")
        .body(Body::from(body))
        .unwrap()
}
