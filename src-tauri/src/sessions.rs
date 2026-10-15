pub const QUICK_EXIT_SECONDS: f64 = 5.0;
pub const MIN_RECORDED_SECONDS: f64 = 30.0;

pub fn recordable_seconds(elapsed: f64) -> u64 {
    if elapsed >= MIN_RECORDED_SECONDS {
        elapsed.floor() as u64
    } else {
        0
    }
}

pub fn quick_failure_message(title: &str, code: Option<i32>, elapsed: f64) -> Option<String> {
    let code = code?;
    if code == 0 || elapsed >= QUICK_EXIT_SECONDS {
        return None;
    }
    if code < 0 {
        return Some(format!(
            "{title} was stopped by signal {} right after launch.",
            -code
        ));
    }
    Some(format!(
        "{title} closed right away (exit code {code}). Check the emulator and BIOS in Settings › Emulation."
    ))
}

pub fn format_play_time(seconds: f64) -> String {
    let total = seconds.floor() as u64;
    if total < 60 {
        return String::new();
    }
    let hours = total / 3600;
    let minutes = (total % 3600) / 60;
    if hours == 0 {
        return format!("{minutes}m");
    }
    if minutes == 0 {
        return format!("{hours}h");
    }
    format!("{hours}h {minutes:02}m")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recordable_seconds_threshold() {
        assert_eq!(recordable_seconds(29.0), 0);
        assert_eq!(recordable_seconds(30.0), 30);
    }

    #[test]
    fn format_play_time_labels() {
        assert_eq!(format_play_time(0.0), "");
        assert_eq!(format_play_time(60.0), "1m");
        assert_eq!(format_play_time(3600.0), "1h");
        assert_eq!(format_play_time(3.0 * 3600.0 + 5.0 * 60.0), "3h 05m");
    }
}
