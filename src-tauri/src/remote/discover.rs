use std::process::Command;
use serde::Serialize;

const SERVICE_TYPE: &str = "_kabin._tcp";

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
    let _ = timeout_secs;
    parse_avahi_hosts(&String::from_utf8_lossy(&output.stdout))
}

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
}
