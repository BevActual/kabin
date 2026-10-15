use serde::Serialize;
use serde_json::{json, Value};

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct EmulationPresetDto {
    pub id: String,
    pub name: String,
    pub description: String,
}

const PRESETS: &[(&str, &str, &str, bool, bool, bool, bool)] = &[
    (
        "balanced",
        "Balanced",
        "Smooth defaults with original scaling where practical.",
        true,
        true,
        false,
        false,
    ),
    (
        "original",
        "Original Hardware",
        "Integer-scaled pixels and conservative features.",
        true,
        true,
        true,
        false,
    ),
    (
        "quality",
        "Quality",
        "Presentation-focused defaults for modern displays.",
        true,
        true,
        false,
        true,
    ),
    (
        "performance",
        "Performance",
        "Reduced extras for slower hardware.",
        true,
        false,
        false,
        false,
    ),
];

pub fn list_presets() -> Vec<EmulationPresetDto> {
    PRESETS
        .iter()
        .map(|(id, name, description, ..)| EmulationPresetDto {
            id: (*id).into(),
            name: (*name).into(),
            description: (*description).into(),
        })
        .collect()
}

pub fn settings_for_preset(preset_id: &str) -> Value {
    let preset = PRESETS
        .iter()
        .find(|(id, ..)| *id == preset_id)
        .unwrap_or(&PRESETS[0]);
    let (id, _, _, fullscreen, vsync, integer_scaling, rewind) = preset;
    json!({
        "preset": id,
        "fullscreen": fullscreen,
        "vsync": vsync,
        "integer_scaling": integer_scaling,
        "rewind": rewind,
    })
}

pub fn apply_preset_to_config(config: &mut crate::config::KabinConfig, preset_id: &str) {
    let bios = config
        .emulation_settings()
        .and_then(|e| e.get("bios"))
        .cloned();
    let mut settings = settings_for_preset(preset_id);
    if let Some(bios) = bios {
        if let Some(obj) = settings.as_object_mut() {
            obj.insert("bios".into(), bios);
        }
    }
    let root = config.data.as_object_mut().expect("config root");
    root.insert("emulation".into(), settings);
}
