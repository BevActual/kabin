use std::net::IpAddr;
#[cfg(not(windows))]
use std::process::Command;
use std::time::{Duration, Instant};

use mdns_sd::{ServiceDaemon, ServiceEvent, ServiceInfo};
use serde::Serialize;

#[cfg_attr(windows, allow(dead_code))]
const SERVICE_TYPE: &str = "_kabin._tcp";
const MDNS_TYPE: &str = "_kabin._tcp.local.";

pub struct LanAdvertiser {
    daemon: ServiceDaemon,
}

impl LanAdvertiser {
    pub fn start(name: &str, port: u16, fingerprint: &str, streaming_ready: bool) -> Option<Self> {
        let daemon = ServiceDaemon::new().ok()?;
        let host = mdns_hostname(name);
        let mut properties = std::collections::HashMap::new();
        properties.insert("protocol".to_string(), "1".to_string());
        properties.insert("tls".to_string(), "1".to_string());
        properties.insert("fingerprint".to_string(), fingerprint.to_string());
        if streaming_ready {
            properties.insert("streaming".to_string(), "kabin".to_string());
        }
        let info = ServiceInfo::new(MDNS_TYPE, name, &host, "", port, properties).ok()?;
        daemon.register(info).ok()?;
        Some(Self { daemon })
    }
}

impl Drop for LanAdvertiser {
    fn drop(&mut self) {
        let _ = self.daemon.shutdown();
    }
}

fn mdns_hostname(name: &str) -> String {
    let mut host: String = name
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() {
                c.to_ascii_lowercase()
            } else {
                '-'
            }
        })
        .collect();
    while host.contains("--") {
        host = host.replace("--", "-");
    }
    let host = host.trim_matches('-');
    let host = if host.is_empty() { "kabin" } else { host };
    format!("{host}.local.")
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DiscoveredHost {
    pub name: String,
    pub address: String,
    pub port: u16,
    pub tls: bool,
    pub fingerprint: String,
}

pub fn discover_nearby_hosts(timeout_secs: u64) -> Vec<DiscoveredHost> {
    let mut hosts = discover_mdns(timeout_secs).unwrap_or_default();
    if hosts.is_empty() {
        hosts = discover_avahi();
    }
    hosts
}

fn discover_mdns(timeout_secs: u64) -> Option<Vec<DiscoveredHost>> {
    let daemon = ServiceDaemon::new().ok()?;
    let receiver = daemon.browse(MDNS_TYPE).ok()?;
    let wait = Duration::from_secs(timeout_secs.clamp(1, 3));
    let deadline = Instant::now() + wait;
    let mut hosts = Vec::new();
    let mut seen = std::collections::HashSet::new();
    while Instant::now() < deadline {
        let remaining = deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            break;
        }
        match receiver.recv_timeout(remaining.min(Duration::from_millis(300))) {
            Ok(ServiceEvent::ServiceResolved(info)) => {
                let Some(host) = host_from_resolved(&info) else {
                    continue;
                };
                if seen.insert((host.address.clone(), host.port)) {
                    hosts.push(host);
                }
            }
            Ok(_) => {}
            Err(mdns_sd::RecvTimeoutError::Timeout) => continue,
            Err(mdns_sd::RecvTimeoutError::Disconnected) => break,
        }
    }
    let _ = daemon.shutdown();
    Some(hosts)
}

fn host_from_resolved(info: &mdns_sd::ResolvedService) -> Option<DiscoveredHost> {
    let address = preferred_address(info.get_addresses())?;
    let tls = info.get_property_val_str("tls") == Some("1");
    Some(DiscoveredHost {
        name: instance_name(info.get_fullname()),
        address,
        port: info.get_port(),
        tls,
        fingerprint: info
            .get_property_val_str("fingerprint")
            .unwrap_or("")
            .to_string(),
    })
}

fn preferred_address(addresses: &std::collections::HashSet<mdns_sd::ScopedIp>) -> Option<String> {
    let ips: Vec<IpAddr> = addresses.iter().map(|ip| ip.to_ip_addr()).collect();
    ips.iter()
        .find(|ip| match ip {
            IpAddr::V4(v4) => !v4.is_loopback() && !v4.is_link_local(),
            IpAddr::V6(v6) => !v6.is_loopback(),
        })
        .or_else(|| ips.first())
        .map(ToString::to_string)
}

fn instance_name(fullname: &str) -> String {
    fullname
        .split_once("._kabin._tcp")
        .map(|(name, _)| name.trim_end_matches('.'))
        .unwrap_or(fullname)
        .replace("\\032", " ")
}

fn discover_avahi() -> Vec<DiscoveredHost> {
    #[cfg(windows)]
    {
        return Vec::new();
    }
    #[cfg(not(windows))]
    {
    let output = Command::new("avahi-browse")
        .args(["-rtp", SERVICE_TYPE])
        .output()
        .ok();
    let Some(output) = output else {
        return Vec::new();
    };
    if !output.status.success() && output.stdout.is_empty() {
        return Vec::new();
    }
    parse_avahi_hosts(&String::from_utf8_lossy(&output.stdout))
    }
}

#[cfg_attr(windows, allow(dead_code))]
fn parse_avahi_hosts(output: &str) -> Vec<DiscoveredHost> {
    let mut hosts = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for line in output.lines() {
        let fields: Vec<&str> = line.split(';').collect();
        if fields.len() < 9 || fields[0] != "=" || fields[4] != SERVICE_TYPE {
            continue;
        }
        let key = (fields[7], fields[8]);
        if !seen.insert(key) {
            continue;
        }
        let metadata: std::collections::HashMap<String, String> = fields[9..]
            .iter()
            .filter_map(|item| {
                let (k, v) = item.split_once('=')?;
                Some((k.to_string(), v.to_string()))
            })
            .collect();
        let Ok(port) = fields[8].parse::<u16>() else {
            continue;
        };
        hosts.push(DiscoveredHost {
            name: fields[3].to_string(),
            address: fields[7].to_string(),
            port,
            tls: metadata.get("tls").map(|v| v.as_str()) == Some("1"),
            fingerprint: metadata.get("fingerprint").cloned().unwrap_or_default(),
        });
    }
    hosts
}

#[cfg(test)]
mod tests {
    use super::parse_avahi_hosts;

    #[test]
    fn parses_avahi_line() {
        let sample = "=;eth0;IPv4;Office;_kabin._tcp;local;Office.local;192.168.1.2;42424;protocol=1;tls=1;fingerprint=abc123";
        let hosts = parse_avahi_hosts(sample);
        assert_eq!(hosts.len(), 1);
        assert_eq!(hosts[0].address, "192.168.1.2");
        assert_eq!(hosts[0].port, 42424);
        assert!(hosts[0].tls);
        assert_eq!(hosts[0].fingerprint, "abc123");
    }

    #[test]
    fn reads_instance_name_from_mdns_fullname() {
        assert_eq!(
            super::instance_name("Office._kabin._tcp.local."),
            "Office"
        );
        assert_eq!(
            super::instance_name("Living\\032Room._kabin._tcp.local."),
            "Living Room"
        );
    }
}
