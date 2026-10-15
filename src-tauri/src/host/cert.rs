use std::fs;
use std::path::{Path, PathBuf};

use rcgen::generate_simple_self_signed;
use sha2::{Digest, Sha256};

pub fn network_identity_root() -> PathBuf {
    dirs::data_local_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("kabin")
        .join("network")
}

fn fingerprint_from_pem(cert_pem: &str) -> Result<String, String> {
    let mut reader = std::io::BufReader::new(cert_pem.as_bytes());
    let certs = rustls_pemfile::certs(&mut reader)
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())?;
    let der = certs
        .first()
        .ok_or_else(|| "certificate PEM is empty".to_string())?;
    Ok(hex::encode(Sha256::digest(der)))
}

pub fn ensure_host_certificate() -> Result<(PathBuf, PathBuf, String), String> {
    let directory = network_identity_root();
    let certificate = directory.join("host.crt");
    let private_key = directory.join("host.key");
    if certificate.is_file() && private_key.is_file() {
        let cert_pem = fs::read_to_string(&certificate).map_err(|e| e.to_string())?;
        let fingerprint = fingerprint_from_pem(&cert_pem)?;
        return Ok((certificate, private_key, fingerprint));
    }
    fs::create_dir_all(&directory).map_err(|e| e.to_string())?;

    let cert = generate_simple_self_signed(vec!["Kabin Host".to_string()]).map_err(|e| e.to_string())?;
    let cert_pem = cert.cert.pem();
    let key_pem = cert.key_pair.serialize_pem();
    fs::write(&certificate, cert_pem.as_bytes()).map_err(|e| e.to_string())?;
    fs::write(&private_key, key_pem.as_bytes()).map_err(|e| e.to_string())?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&private_key, fs::Permissions::from_mode(0o600))
            .map_err(|e| e.to_string())?;
        fs::set_permissions(&certificate, fs::Permissions::from_mode(0o644))
            .map_err(|e| e.to_string())?;
    }
    let fingerprint = fingerprint_from_pem(&cert_pem)?;
    Ok((certificate, private_key, fingerprint))
}

pub fn load_rustls_config(cert_path: &Path, key_path: &Path) -> Result<rustls::ServerConfig, String> {
    let cert_pem = fs::read(cert_path).map_err(|e| e.to_string())?;
    let key_pem = fs::read(key_path).map_err(|e| e.to_string())?;
    let mut cert_reader = std::io::BufReader::new(cert_pem.as_slice());
    let certs: Vec<_> = rustls_pemfile::certs(&mut cert_reader)
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| e.to_string())?;
    let mut key_reader = std::io::BufReader::new(key_pem.as_slice());
    let key = rustls_pemfile::private_key(&mut key_reader)
        .map_err(|e| e.to_string())?
        .ok_or_else(|| "private key PEM is empty".to_string())?;
    rustls::ServerConfig::builder()
        .with_no_client_auth()
        .with_single_cert(certs, key)
        .map_err(|e| e.to_string())
}
