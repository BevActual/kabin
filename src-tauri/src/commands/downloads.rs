use tauri::State;

use crate::downloads::{
    DownloadEngine, DownloadStatus, Indexer, ReleaseHit, UsenetServer, WantedItem,
};

#[tauri::command]
pub async fn get_download_status(
    engine: State<'_, DownloadEngine>,
) -> Result<DownloadStatus, String> {
    Ok(engine.status().await)
}

#[tauri::command]
pub fn set_download_quality(engine: State<'_, DownloadEngine>, quality: String) -> Result<(), String> {
    engine.set_quality(quality)
}

#[tauri::command]
pub fn set_download_import_dir(
    engine: State<'_, DownloadEngine>,
    path: String,
) -> Result<(), String> {
    engine.set_import_dir(path)
}

#[tauri::command]
pub fn set_download_folder(engine: State<'_, DownloadEngine>, path: String) -> Result<(), String> {
    engine.set_download_dir(path)
}

#[tauri::command]
pub fn set_usenet_connections(
    engine: State<'_, DownloadEngine>,
    connections: u16,
) -> Result<(), String> {
    engine.set_connections(connections)
}

#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UsenetServerInput {
    pub host: String,
    #[serde(default)]
    pub port: u16,
    #[serde(default = "default_ssl")]
    pub ssl: bool,
    #[serde(default)]
    pub username: String,
    #[serde(default)]
    pub password: String,
}

fn default_ssl() -> bool {
    true
}

#[tauri::command]
pub fn save_usenet_server(
    engine: State<'_, DownloadEngine>,
    server: UsenetServerInput,
) -> Result<(), String> {
    engine.save_usenet(UsenetServer {
        host: server.host,
        port: server.port,
        ssl: server.ssl,
        username: server.username,
        password: server.password,
    })
}

#[tauri::command]
pub async fn test_usenet_server(engine: State<'_, DownloadEngine>) -> Result<String, String> {
    engine.test_usenet().await
}

#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IndexerInput {
    #[serde(default)]
    pub id: String,
    pub name: String,
    pub url: String,
    #[serde(default)]
    pub api_key: String,
    pub kind: String,
}

#[tauri::command]
pub fn save_indexer(engine: State<'_, DownloadEngine>, indexer: IndexerInput) -> Result<(), String> {
    engine.upsert_indexer(Indexer {
        id: indexer.id,
        name: indexer.name,
        url: indexer.url,
        api_key: indexer.api_key,
        kind: indexer.kind,
    })
}

#[tauri::command]
pub fn remove_indexer(engine: State<'_, DownloadEngine>, id: String) -> Result<(), String> {
    engine.remove_indexer(&id)
}

#[tauri::command]
pub fn add_wanted(
    engine: State<'_, DownloadEngine>,
    title: String,
    year: String,
    kind: String,
) -> Result<WantedItem, String> {
    engine.add_wanted(title, year, kind)
}

#[tauri::command]
pub fn remove_wanted(engine: State<'_, DownloadEngine>, id: String) -> Result<(), String> {
    engine.remove_wanted(&id)
}

#[tauri::command]
pub async fn search_wanted(
    engine: State<'_, DownloadEngine>,
    id: String,
) -> Result<Vec<ReleaseHit>, String> {
    engine.search_wanted(&id).await
}

#[tauri::command]
pub async fn add_download(
    engine: State<'_, DownloadEngine>,
    link: String,
    name: String,
    protocol: String,
    wanted_id: String,
) -> Result<String, String> {
    engine.add_download(link, name, protocol, wanted_id).await
}

#[tauri::command]
pub async fn download_action(
    engine: State<'_, DownloadEngine>,
    id: String,
    action: String,
) -> Result<(), String> {
    engine.download_action(id, action).await
}
