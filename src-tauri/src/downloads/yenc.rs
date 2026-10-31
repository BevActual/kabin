//! yEnc encode/decode used by Usenet article bodies.
//!
//! Encoding adds 42 to each byte. Bytes that would land on NULL, LF, CR, or
//! `=` are escaped as `=` followed by that byte plus 64.

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct YencPart {
    pub name: String,
    pub begin: u64,
    pub size: u64,
    pub data: Vec<u8>,
}

pub fn decode_yenc(article: &[u8]) -> Result<YencPart, String> {
    let mut name = String::new();
    let mut begin = 1u64;
    let mut size = 0u64;
    let mut data = Vec::new();
    let mut in_data = false;

    for mut line in article.split(|byte| *byte == b'\n') {
        if line.last() == Some(&b'\r') {
            line = &line[..line.len() - 1];
        }
        if let Some(rest) = line.strip_prefix(b"=ybegin ") {
            let header = String::from_utf8_lossy(rest);
            name = field(&header, "name").unwrap_or_default();
            size = field(&header, "size")
                .and_then(|value| value.parse().ok())
                .unwrap_or(0);
            in_data = true;
            continue;
        }
        if let Some(rest) = line.strip_prefix(b"=ypart ") {
            let header = String::from_utf8_lossy(rest);
            if let Some(value) = field(&header, "begin").and_then(|value| value.parse().ok()) {
                begin = value;
            }
            continue;
        }
        if line.starts_with(b"=yend ") {
            break;
        }
        if !in_data || line.is_empty() {
            continue;
        }
        decode_line(line, &mut data);
    }

    if name.is_empty() && data.is_empty() {
        return Err("Article is not yEnc".into());
    }
    Ok(YencPart {
        name,
        begin,
        size,
        data,
    })
}

fn decode_line(line: &[u8], out: &mut Vec<u8>) {
    let mut index = 0;
    while index < line.len() {
        let byte = line[index];
        if byte == b'=' {
            index += 1;
            if index >= line.len() {
                break;
            }
            out.push(line[index].wrapping_sub(64).wrapping_sub(42));
        } else {
            out.push(byte.wrapping_sub(42));
        }
        index += 1;
    }
}

fn field(header: &str, key: &str) -> Option<String> {
    for part in header.split_whitespace() {
        if let Some(value) = part.strip_prefix(&format!("{key}=")) {
            return Some(value.to_string());
        }
    }
    None
}

pub fn encode_yenc(name: &str, data: &[u8]) -> Vec<u8> {
    let mut out = format!("=ybegin line=128 size={} name={name}\r\n", data.len()).into_bytes();
    let mut column = 0;
    for &byte in data {
        let encoded = byte.wrapping_add(42);
        let critical = matches!(encoded, 0 | b'\n' | b'\r' | b'=');
        if critical {
            out.push(b'=');
            out.push(encoded.wrapping_add(64));
            column += 2;
        } else {
            out.push(encoded);
            column += 1;
        }
        if column >= 128 {
            out.extend_from_slice(b"\r\n");
            column = 0;
        }
    }
    if column != 0 {
        out.extend_from_slice(b"\r\n");
    }
    out.extend_from_slice(format!("=yend size={}\r\n", data.len()).as_bytes());
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip_plain_and_escaped_bytes() {
        let mut data: Vec<u8> = (0u8..=255).collect();
        data.extend_from_slice(b"Hello Kabin");
        let encoded = encode_yenc("clip.bin", &data);
        let decoded = decode_yenc(&encoded).unwrap();
        assert_eq!(decoded.name, "clip.bin");
        assert_eq!(decoded.begin, 1);
        assert_eq!(decoded.data, data);
    }

    #[test]
    fn decodes_a_known_byte() {
        let article = b"=ybegin line=128 size=1 name=a.txt\r\nk\r\n=yend size=1\r\n";
        let decoded = decode_yenc(article).unwrap();
        assert_eq!(decoded.data, b"A");
        assert_eq!(decoded.name, "a.txt");
    }
}
