use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};

use regex::Regex;
use serde_json::Value;
use sha2::{Digest, Sha256};

#[derive(Debug, Clone, Copy)]
pub struct RuntimeSpec {
    pub id: &'static str,
    pub name: &'static str,
    pub repository: &'static str,
    pub systems: &'static [&'static str],
    pub asset_patterns: &'static [(&'static str, &'static str)],
}

const RUNTIMES: &[RuntimeSpec] = &[
    RuntimeSpec {
        id: "duckstation",
        name: "DuckStation",
        repository: "stenzek/duckstation",
        systems: &["ps1"],
        asset_patterns: &[
            ("x86_64", r"DuckStation-x64\.AppImage$"),
            ("aarch64", r"arm64.*\.AppImage$"),
        ],
    },
    RuntimeSpec {
        id: "pcsx2",
        name: "PCSX2",
        repository: "PCSX2/pcsx2",
        systems: &["ps2"],
        asset_patterns: &[
            ("x86_64", r"(?:x64|x86_64).*\.AppImage$"),
            ("aarch64", r"(?:arm64|aarch64).*\.AppImage$"),
        ],
    },
    RuntimeSpec {
        id: "ppsspp",
        name: "PPSSPP",
        repository: "hrydgard/ppsspp",
        systems: &["psp"],
        asset_patterns: &[
            ("x86_64", r"anylinux-x86_64\.AppImage$"),
            ("aarch64", r"anylinux-aarch64\.AppImage$"),
        ],
    },
];

pub fn runtime_by_id(id: &str) -> Option<&'static RuntimeSpec> {
    RUNTIMES.iter().find(|r| r.id == id)
}

pub fn managed_downloads_supported() -> bool {
    // Official managed builds are Linux AppImages. Windows uses installed emulators.
    cfg!(not(windows))
}

pub fn recommended_runtime(system_id: &str) -> Option<&'static RuntimeSpec> {
    if !managed_downloads_supported() {
        return None;
    }
    RUNTIMES.iter().find(|r| r.systems.contains(&system_id))
}

pub fn runtime_root() -> PathBuf {
    #[cfg(unix)]
    if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
        if !xdg.is_empty() {
            return PathBuf::from(xdg).join("kabin").join("emulators");
        }
    }
    let base = dirs::data_dir()
        .unwrap_or_else(|| dirs::home_dir().unwrap_or_default().join(".local/share"));
    base.join("kabin").join("emulators")
}

pub fn architecture() -> String {
    let machine = std::env::consts::ARCH;
    match machine {
        "x86_64" | "aarch64" => machine.to_string(),
        other => other.to_string(),
    }
}

pub fn installed_executable(runtime_id: &str) -> Option<PathBuf> {
    installed_executable_at(runtime_id, &runtime_root())
}

pub fn installed_executable_at(runtime_id: &str, root: &Path) -> Option<PathBuf> {
    let executable = root.join(runtime_id).join(runtime_id);
    if crate::platform::is_executable(&executable) {
        return Some(executable);
    }
    None
}

#[derive(Debug, Clone)]
pub struct ResolvedAsset {
    pub name: String,
    pub url: String,
    pub sha256: String,
    pub version: String,
}

pub fn resolve_asset(spec: &RuntimeSpec) -> Result<ResolvedAsset, String> {
    let arch = architecture();
    let pattern = spec
        .asset_patterns
        .iter()
        .find(|(a, _)| *a == arch)
        .map(|(_, p)| *p)
        .ok_or_else(|| format!("{} has no managed build for {arch}", spec.name))?;
    let re = Regex::new(&format!("(?i){pattern}")).map_err(|e| e.to_string())?;

    let release_url = format!(
        "https://api.github.com/repos/{}/releases/latest",
        spec.repository
    );
    let release: Value = github_json(&release_url)?;
    let assets = release
        .get("assets")
        .and_then(|v| v.as_array())
        .ok_or_else(|| format!("No release assets for {}", spec.name))?;

    let asset = assets
        .iter()
        .find(|item| {
            item.get("name")
                .and_then(|v| v.as_str())
                .is_some_and(|name| re.is_match(name))
        })
        .ok_or_else(|| format!("No compatible {} release asset was found", spec.name))?;

    let digest = asset
        .get("digest")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let sha256 = digest
        .strip_prefix("sha256:")
        .filter(|_| digest.starts_with("sha256:"))
        .ok_or_else(|| format!("{} did not publish a verifiable SHA-256 digest", spec.name))?
        .to_string();

    Ok(ResolvedAsset {
        name: asset
            .get("name")
            .and_then(|v| v.as_str())
            .unwrap_or("asset")
            .to_string(),
        url: asset
            .get("browser_download_url")
            .and_then(|v| v.as_str())
            .ok_or_else(|| "Missing download URL".to_string())?
            .to_string(),
        sha256,
        version: release
            .get("tag_name")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown")
            .to_string(),
    })
}

fn github_json(url: &str) -> Result<Value, String> {
    let agent = ureq::AgentBuilder::new()
        .user_agent("Kabin/0.1")
        .timeout(std::time::Duration::from_secs(15))
        .build();
    let response = agent
        .get(url)
        .set("Accept", "application/vnd.github+json")
        .set("X-GitHub-Api-Version", "2022-11-28")
        .call()
        .map_err(|e| format!("GitHub request failed: {e}"))?;
    let mut body = String::new();
    response
        .into_reader()
        .read_to_string(&mut body)
        .map_err(|e| e.to_string())?;
    serde_json::from_str(&body).map_err(|e| e.to_string())
}

pub fn install_runtime(spec: &RuntimeSpec) -> Result<PathBuf, String> {
    let asset = resolve_asset(spec)?;
    install_runtime_asset(spec, &asset, &runtime_root())
}

pub fn install_runtime_asset(
    spec: &RuntimeSpec,
    asset: &ResolvedAsset,
    root: &Path,
) -> Result<PathBuf, String> {
    let agent = ureq::AgentBuilder::new()
        .user_agent("Kabin/0.1")
        .timeout(std::time::Duration::from_secs(120))
        .build();
    let response = agent
        .get(&asset.url)
        .call()
        .map_err(|e| format!("Download failed: {e}"))?;

    let mut digest = Sha256::new();
    let mut reader = response.into_reader();
    let mut payload = Vec::new();
    let mut buffer = [0u8; 1024 * 1024];
    loop {
        let read = reader.read(&mut buffer).map_err(|e| e.to_string())?;
        if read == 0 {
            break;
        }
        digest.update(&buffer[..read]);
        payload.extend_from_slice(&buffer[..read]);
    }

    install_verified_payload(spec, asset, root, &payload)
}

pub fn install_verified_payload(
    spec: &RuntimeSpec,
    asset: &ResolvedAsset,
    root: &Path,
    payload: &[u8],
) -> Result<PathBuf, String> {
    let hex = hex::encode(Sha256::digest(payload));
    if hex != asset.sha256 {
        return Err(format!(
            "{} download failed checksum verification",
            spec.name
        ));
    }

    let directory = root.join(spec.id);
    fs::create_dir_all(&directory).map_err(|e| e.to_string())?;
    let destination = directory.join(spec.id);
    let temporary = directory.join(format!(".{}.download", spec.id));

    fs::write(&temporary, payload).map_err(|e| e.to_string())?;
    crate::platform::make_user_executable(&temporary)?;
    fs::rename(&temporary, &destination).map_err(|e| e.to_string())?;

    let metadata = serde_json::json!({
        "name": asset.name,
        "url": asset.url,
        "sha256": asset.sha256,
        "version": asset.version,
    });
    fs::write(
        directory.join("runtime.json"),
        format!("{}\n", serde_json::to_string_pretty(&metadata).unwrap_or_default()),
    )
    .map_err(|e| e.to_string())?;

    Ok(destination)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recommends_duckstation_for_ps1() {
        if !managed_downloads_supported() {
            assert!(recommended_runtime("ps1").is_none());
            return;
        }
        assert_eq!(recommended_runtime("ps1").unwrap().id, "duckstation");
    }

    #[test]
    fn does_not_recommend_mgba() {
        assert!(recommended_runtime("gba").is_none());
    }

    #[test]
    fn refuses_release_without_digest() {
        let spec = runtime_by_id("duckstation").unwrap();
        let release = serde_json::json!({
            "tag_name": "v1",
            "assets": [{
                "name": "DuckStation-x64.AppImage",
                "browser_download_url": "https://example.invalid/duckstation"
            }]
        });
        let re = Regex::new(r"(?i)DuckStation-x64\.AppImage$").unwrap();
        let assets = release["assets"].as_array().unwrap();
        let asset = assets.iter().find(|item| {
            item.get("name")
                .and_then(|v| v.as_str())
                .is_some_and(|name| re.is_match(name))
        });
        assert!(asset.is_some());
        let digest = asset.unwrap().get("digest").and_then(|v| v.as_str()).unwrap_or("");
        assert!(!digest.starts_with("sha256:"));
    }

    #[test]
    fn installs_verified_runtime_atomically() {
        let spec = runtime_by_id("duckstation").unwrap();
        let payload = b"verified appimage";
        let checksum = hex::encode(Sha256::digest(payload));
        let asset = ResolvedAsset {
            name: "DuckStation-x64.AppImage".into(),
            url: "unused".into(),
            sha256: checksum.clone(),
            version: "v1".into(),
        };
        let dir = std::env::temp_dir().join(format!("kabin-managed-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        let root = &dir;

        let executable = install_verified_payload(spec, &asset, root, payload).unwrap();
        assert_eq!(fs::read(&executable).unwrap(), payload);
        assert_eq!(installed_executable_at("duckstation", root).unwrap(), executable);
        assert!(!root.join("duckstation").join(".duckstation.download").exists());
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn checksum_mismatch_does_not_install() {
        let spec = runtime_by_id("duckstation").unwrap();
        let asset = ResolvedAsset {
            name: "DuckStation-x64.AppImage".into(),
            url: "unused".into(),
            sha256: "0".repeat(64),
            version: "v1".into(),
        };
        let dir = std::env::temp_dir().join(format!("kabin-managed-bad-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        let err = install_verified_payload(spec, &asset, &dir, b"tampered").unwrap_err();
        assert!(err.contains("checksum"));
        assert!(installed_executable_at("duckstation", &dir).is_none());
        let _ = fs::remove_dir_all(&dir);
    }
}
