use roxmltree::Node;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NzbSegment {
    pub number: u32,
    pub bytes: u64,
    pub message_id: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NzbFile {
    pub name: String,
    pub groups: Vec<String>,
    pub segments: Vec<NzbSegment>,
}

pub fn parse_nzb(xml: &str) -> Result<Vec<NzbFile>, String> {
    let doc = roxmltree::Document::parse(xml).map_err(|e| format!("Could not read NZB: {e}"))?;
    let mut files = Vec::new();
    for node in doc.descendants().filter(|node| is_name(node, "file")) {
        let subject = node.attribute("subject").unwrap_or("");
        let mut groups = Vec::new();
        let mut segments = Vec::new();
        for child in node.descendants() {
            if is_name(&child, "group") {
                if let Some(name) = child.text() {
                    let name = name.trim();
                    if !name.is_empty() {
                        groups.push(name.to_string());
                    }
                }
            } else if is_name(&child, "segment") {
                let number = child
                    .attribute("number")
                    .and_then(|value| value.parse().ok())
                    .unwrap_or(0);
                let bytes = child
                    .attribute("bytes")
                    .and_then(|value| value.parse().ok())
                    .unwrap_or(0);
                let message_id = normalize_message_id(child.text().unwrap_or(""));
                if message_id.is_empty() {
                    continue;
                }
                segments.push(NzbSegment {
                    number,
                    bytes,
                    message_id,
                });
            }
        }
        segments.sort_by_key(|segment| segment.number);
        if segments.is_empty() {
            continue;
        }
        files.push(NzbFile {
            name: filename_from_subject(subject),
            groups,
            segments,
        });
    }
    if files.is_empty() {
        return Err("NZB did not contain any files".into());
    }
    Ok(files)
}

fn is_name(node: &Node<'_, '_>, name: &str) -> bool {
    node.is_element() && node.tag_name().name() == name
}

fn normalize_message_id(value: &str) -> String {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return String::new();
    }
    if trimmed.starts_with('<') && trimmed.ends_with('>') {
        trimmed.to_string()
    } else {
        format!("<{trimmed}>")
    }
}

fn filename_from_subject(subject: &str) -> String {
    if let Some(start) = subject.find('"') {
        if let Some(end) = subject[start + 1..].find('"') {
            let quoted = &subject[start + 1..start + 1 + end];
            if !quoted.is_empty() {
                return quoted.to_string();
            }
        }
    }
    subject
        .split_whitespace()
        .find(|token| !token.contains("yEnc") && !token.starts_with('('))
        .unwrap_or("download")
        .to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_files_segments_and_quoted_names() {
        let xml = r#"
            <nzb>
              <file subject="&quot;Feature.mkv&quot; yEnc (1/2)">
                <groups><group>alt.binaries.example</group></groups>
                <segments>
                  <segment bytes="10" number="2">part2@example</segment>
                  <segment bytes="10" number="1">&lt;part1@example&gt;</segment>
                </segments>
              </file>
            </nzb>
        "#;
        let files = parse_nzb(xml).unwrap();
        assert_eq!(files.len(), 1);
        assert_eq!(files[0].name, "Feature.mkv");
        assert_eq!(files[0].groups, vec!["alt.binaries.example".to_string()]);
        assert_eq!(files[0].segments[0].number, 1);
        assert_eq!(files[0].segments[0].message_id, "<part1@example>");
        assert_eq!(files[0].segments[1].message_id, "<part2@example>");
    }
}
