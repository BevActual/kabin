use std::sync::Arc;
use std::time::Duration;

use rustls::ClientConfig;
use rustls::RootCertStore;
use rustls::pki_types::ServerName;
use tokio::io::{AsyncBufRead, AsyncBufReadExt, AsyncWrite, AsyncWriteExt, BufReader};
use tokio::net::TcpStream;
use tokio_rustls::TlsConnector;

use super::settings::UsenetServer;

pub struct NntpConn {
    reader: Box<dyn AsyncBufRead + Unpin + Send>,
    writer: Box<dyn AsyncWrite + Unpin + Send>,
}

impl NntpConn {
    pub async fn connect(server: &UsenetServer) -> Result<Self, String> {
        let host = server.host.trim();
        if host.is_empty() {
            return Err("Add a Usenet server in Settings".into());
        }
        if host.chars().any(|c| c.is_whitespace()) {
            return Err("Server address cannot contain spaces".into());
        }
        let port = server.resolved_port();
        let address = format!("{host}:{port}");
        let stream = tokio::time::timeout(Duration::from_secs(20), TcpStream::connect(&address))
            .await
            .map_err(|_| format!("Timed out connecting to {host}"))?
            .map_err(|e| format!("Could not connect to {host}: {e}"))?;

        let (reader, writer): (
            Box<dyn AsyncBufRead + Unpin + Send>,
            Box<dyn AsyncWrite + Unpin + Send>,
        ) = if server.ssl {
            let name = ServerName::try_from(host.to_string())
                .map_err(|_| format!("{host} is not a valid server name"))?;
            let tls = TlsConnector::from(tls_config())
                .connect(name, stream)
                .await
                .map_err(|e| format!("Could not start TLS with {host}: {e}"))?;
            let (read, write) = tokio::io::split(tls);
            (Box::new(BufReader::new(read)), Box::new(write))
        } else {
            let (read, write) = stream.into_split();
            (Box::new(BufReader::new(read)), Box::new(write))
        };

        let mut conn = Self { reader, writer };
        let greeting = conn.read_status().await?;
        if !greeting.starts_with("200") && !greeting.starts_with("201") {
            return Err(format!("Usenet server refused the connection: {greeting}"));
        }
        conn.authenticate(server).await?;
        Ok(conn)
    }

    pub async fn command(&mut self, command: &str) -> Result<String, String> {
        self.writer
            .write_all(format!("{command}\r\n").as_bytes())
            .await
            .map_err(|e| e.to_string())?;
        self.writer.flush().await.map_err(|e| e.to_string())?;
        self.read_status().await
    }

    pub async fn body(&mut self, message_id: &str) -> Result<Vec<u8>, String> {
        let status = self.command(&format!("BODY {message_id}")).await?;
        if !status.starts_with("222") && !status.starts_with("220") {
            return Err(status);
        }
        let mut article = Vec::new();
        loop {
            let line = read_line(&mut self.reader).await?;
            if line == b"." {
                break;
            }
            let data = if line.first() == Some(&b'.') {
                &line[1..]
            } else {
                line.as_slice()
            };
            article.extend_from_slice(data);
            article.extend_from_slice(b"\n");
        }
        Ok(article)
    }

    async fn authenticate(&mut self, server: &UsenetServer) -> Result<(), String> {
        let username = server.username.trim();
        if username.is_empty() {
            return Ok(());
        }
        if username.contains(['\r', '\n']) || server.password.contains(['\r', '\n']) {
            return Err("Usenet username or password contains a line break".into());
        }
        let status = self.command(&format!("AUTHINFO USER {username}")).await?;
        if status.starts_with("281") {
            return Ok(());
        }
        if !status.starts_with("381") {
            return Err(format!("Usenet login failed: {status}"));
        }
        let status = self
            .command(&format!("AUTHINFO PASS {}", server.password))
            .await?;
        if status.starts_with("281") {
            Ok(())
        } else {
            Err(format!("Usenet login failed: {status}"))
        }
    }

    async fn read_status(&mut self) -> Result<String, String> {
        let line = read_line(&mut self.reader).await?;
        String::from_utf8(line).map_err(|_| "Usenet server sent a status line that was not text".into())
    }
}

fn tls_config() -> Arc<ClientConfig> {
    static CONFIG: std::sync::OnceLock<Arc<ClientConfig>> = std::sync::OnceLock::new();
    CONFIG
        .get_or_init(|| {
            let mut roots = RootCertStore::empty();
            roots.extend(webpki_roots::TLS_SERVER_ROOTS.iter().cloned());
            Arc::new(
                ClientConfig::builder()
                    .with_root_certificates(roots)
                    .with_no_client_auth(),
            )
        })
        .clone()
}

async fn read_line<R: AsyncBufRead + Unpin>(reader: &mut R) -> Result<Vec<u8>, String> {
    let mut buf = Vec::new();
    let read = reader
        .read_until(b'\n', &mut buf)
        .await
        .map_err(|e| e.to_string())?;
    if read == 0 {
        return Err("Usenet server closed the connection".into());
    }
    if buf.last() == Some(&b'\n') {
        buf.pop();
    }
    if buf.last() == Some(&b'\r') {
        buf.pop();
    }
    Ok(buf)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::downloads::yenc::encode_yenc;
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::TcpListener;

    #[tokio::test]
    async fn downloads_a_yenc_body_from_a_local_server() {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let port = listener.local_addr().unwrap().port();
        let payload = encode_yenc("hello.txt", b"A");
        tokio::spawn(async move {
            let (mut socket, _) = listener.accept().await.unwrap();
            socket.write_all(b"200 test\r\n").await.unwrap();
            let mut buf = vec![0u8; 1024];
            loop {
                let n = socket.read(&mut buf).await.unwrap();
                if n == 0 {
                    break;
                }
                let text = String::from_utf8_lossy(&buf[..n]);
                if text.contains("GROUP") {
                    socket.write_all(b"211 1 1 1 alt.binaries.test\r\n").await.unwrap();
                }
                if text.contains("BODY") {
                    socket.write_all(b"222 0 <a@test>\r\n").await.unwrap();
                    socket.write_all(&payload).await.unwrap();
                    socket.write_all(b".\r\n").await.unwrap();
                    break;
                }
            }
        });

        let server = UsenetServer {
            host: "127.0.0.1".into(),
            port,
            ssl: false,
            username: String::new(),
            password: String::new(),
        };
        let mut conn = NntpConn::connect(&server).await.unwrap();
        let _ = conn.command("GROUP alt.binaries.test").await.unwrap();
        let article = conn.body("<a@test>").await.unwrap();
        let decoded = crate::downloads::yenc::decode_yenc(&article).unwrap();
        assert_eq!(decoded.data, b"A");
    }
}
