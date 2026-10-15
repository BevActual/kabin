use std::io::{Read, Write};
use std::net::TcpStream;
use std::sync::Arc;
use std::time::Duration;

use serde_json::Value;

use super::tls;
use crate::config::RemoteHostEntry;

const DEFAULT_TIMEOUT: Duration = Duration::from_secs(8);

pub fn host_url(host: &RemoteHostEntry, path: &str) -> String {
    let scheme = if host.tls { "https" } else { "http" };
    format!("{}://{}:{}{}", scheme, host.address, host.port, path)
}

pub fn pair_with_host(
    host: &RemoteHostEntry,
    code: &str,
    device_name: &str,
) -> Result<Value, String> {
    let body = serde_json::json!({
        "code": code,
        "device_name": device_name,
    });
    post_json(host, "/v1/pair", None, &body)
}

pub fn fetch_remote_library(host: &RemoteHostEntry, token: &str) -> Result<Value, String> {
    get_json(host, "/v1/library", Some(token))
}

pub fn fetch_remote_stream(
    host: &RemoteHostEntry,
    token: &str,
    item_id: &str,
    track: u32,
) -> Result<Vec<u8>, String> {
    let query = if track > 0 {
        format!(
            "/v1/media/stream?id={}&track={track}",
            urlencoding(item_id)
        )
    } else {
        format!("/v1/media/stream?id={}", urlencoding(item_id))
    };
    get_bytes(host, &query, Some(token), Duration::from_secs(300))
}

fn urlencoding(value: &str) -> String {
    value
        .chars()
        .map(|c| match c {
            'A'..='Z' | 'a'..='z' | '0'..='9' | '-' | '_' | '.' | '~' => c.to_string(),
            _ => format!("%{:02X}", c as u8),
        })
        .collect()
}

fn get_json(host: &RemoteHostEntry, path: &str, token: Option<&str>) -> Result<Value, String> {
    let bytes = get_bytes(host, path, token, DEFAULT_TIMEOUT)?;
    serde_json::from_slice(&bytes).map_err(|e| e.to_string())
}

fn post_json(
    host: &RemoteHostEntry,
    path: &str,
    token: Option<&str>,
    body: &Value,
) -> Result<Value, String> {
    let payload = serde_json::to_vec(body).map_err(|e| e.to_string())?;
    let bytes = request(host, "POST", path, token, Some(payload), DEFAULT_TIMEOUT)?;
    serde_json::from_slice(&bytes).map_err(|e| e.to_string())
}

fn get_bytes(
    host: &RemoteHostEntry,
    path: &str,
    token: Option<&str>,
    timeout: Duration,
) -> Result<Vec<u8>, String> {
    request(host, "GET", path, token, None, timeout)
}

fn request(
    host: &RemoteHostEntry,
    method: &str,
    path: &str,
    token: Option<&str>,
    body: Option<Vec<u8>>,
    timeout: Duration,
) -> Result<Vec<u8>, String> {
    if !host.tls {
        return Err("Only TLS Kabin hosts are supported".into());
    }
    let addr = format!("{}:{}", host.address, host.port);
    let mut stream = TcpStream::connect(&addr).map_err(|e| e.to_string())?;
    stream
        .set_read_timeout(Some(timeout))
        .map_err(|e| e.to_string())?;
    stream
        .set_write_timeout(Some(timeout))
        .map_err(|e| e.to_string())?;

    let config = tls::client_config(&host.fingerprint)?;
    let server_name = server_name_for_host(&host.address)?;
    let mut connection = rustls::ClientConnection::new(Arc::new(config), server_name)
        .map_err(|e| e.to_string())?;
    let mut tls_stream = rustls::Stream::new(&mut connection, &mut stream);

    let mut request = format!("{method} {path} HTTP/1.1\r\nHost: {}\r\n", host.address);
    if let Some(token) = token {
        request.push_str(&format!("Authorization: Bearer {token}\r\n"));
    }
    if let Some(body) = &body {
        request.push_str("Content-Type: application/json\r\n");
        request.push_str(&format!("Content-Length: {}\r\n", body.len()));
    }
    request.push_str("Connection: close\r\n\r\n");
    tls_stream
        .write_all(request.as_bytes())
        .map_err(|e| e.to_string())?;
    if let Some(body) = body {
        tls_stream.write_all(&body).map_err(|e| e.to_string())?;
    }
    tls_stream.flush().map_err(|e| e.to_string())?;

    let mut response = Vec::new();
    tls_stream
        .read_to_end(&mut response)
        .map_err(|e| e.to_string())?;
    parse_http_response(&response)
}

fn server_name_for_host(address: &str) -> Result<rustls::pki_types::ServerName<'static>, String> {
    if let Ok(ip) = address.parse::<std::net::IpAddr>() {
        return Ok(rustls::pki_types::ServerName::IpAddress(ip.into()));
    }
    let leaked: &'static str = Box::leak(address.to_string().into_boxed_str());
    rustls::pki_types::ServerName::try_from(leaked)
        .map_err(|_| "Invalid host address".to_string())
}

fn parse_http_response(raw: &[u8]) -> Result<Vec<u8>, String> {
    let Some(header_end) = raw.windows(4).position(|w| w == b"\r\n\r\n") else {
        return Err("Invalid HTTP response".into());
    };
    let header = std::str::from_utf8(&raw[..header_end]).map_err(|e| e.to_string())?;
    let status_line = header.lines().next().unwrap_or("");
    let status = status_line
        .split_whitespace()
        .nth(1)
        .and_then(|s| s.parse::<u16>().ok())
        .unwrap_or(0);
    let body = raw[(header_end + 4)..].to_vec();
    if (200..300).contains(&status) {
        return Ok(body);
    }
    if status == 401 || status == 403 {
        return Err("Re-pair required".into());
    }
    if let Ok(json) = serde_json::from_slice::<Value>(&body) {
        if let Some(err) = json.get("error").and_then(|v| v.as_str()) {
            return Err(format!("HTTP {status}: {err}"));
        }
    }
    Err(format!("HTTP {status}"))
}
