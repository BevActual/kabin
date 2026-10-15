use std::path::Path;

pub fn connected_controllers() -> Vec<String> {
    let input_dir = Path::new("/dev/input/by-id");
    let Ok(read) = std::fs::read_dir(input_dir) else {
        return Vec::new();
    };
    let mut names = Vec::new();
    for entry in read.flatten() {
        let name = entry.file_name().to_string_lossy().into_owned();
        if !name.ends_with("-event-joystick") {
            continue;
        }
        let mut label = name.trim_end_matches("-event-joystick").to_string();
        label = label.replace("usb-", "");
        label = label.replace('_', " ");
        if !names.contains(&label) {
            names.push(label);
        }
    }
    names.sort();
    names
}
