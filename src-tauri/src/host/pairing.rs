use std::time::{Duration, Instant};

use rand::Rng;
use subtle::ConstantTimeEq;

const PAIR_WINDOW: Duration = Duration::from_secs(30);
const PAIR_MAX_FAILURES: usize = 8;

#[derive(Default)]
pub struct PairingState {
    pub code: Option<String>,
    pub expires_at: Option<f64>,
    expires_mono: Option<Instant>,
    failures: Vec<Instant>,
}

impl PairingState {
    pub fn create_code(&mut self, lifetime_secs: u64) -> String {
        let code = format!("{:06}", rand::thread_rng().gen_range(0..1_000_000));
        self.code = Some(code.clone());
        let mono = Instant::now() + Duration::from_secs(lifetime_secs);
        self.expires_mono = Some(mono);
        self.expires_at = Some(
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_secs_f64() + lifetime_secs as f64)
                .unwrap_or(0.0),
        );
        code
    }

    pub fn attempt(&mut self, code: &str) -> PairingOutcome {
        let now = Instant::now();
        self.failures
            .retain(|stamp| now.duration_since(*stamp) < PAIR_WINDOW);
        if self.failures.len() >= PAIR_MAX_FAILURES {
            return PairingOutcome::Locked;
        }
        let Some(expected) = self.code.as_ref() else {
            self.failures.push(now);
            return PairingOutcome::Invalid;
        };
        let Some(expires) = self.expires_mono else {
            self.failures.push(now);
            return PairingOutcome::Invalid;
        };
        if now > expires {
            self.code = None;
            self.expires_mono = None;
            self.expires_at = None;
            self.failures.push(now);
            return PairingOutcome::Invalid;
        }
        let supplied = pairing_bytes(code);
        let expected_bytes = pairing_bytes(expected);
        if supplied.ct_eq(&expected_bytes).into() {
            self.code = None;
            self.expires_mono = None;
            self.expires_at = None;
            self.failures.clear();
            return PairingOutcome::Ok;
        }
        self.failures.push(now);
        PairingOutcome::Invalid
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PairingOutcome {
    Ok,
    Invalid,
    Locked,
}

fn pairing_bytes(value: &str) -> Vec<u8> {
    value.as_bytes().to_vec()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pairing_accepts_valid_code_once() {
        let mut state = PairingState::default();
        let code = state.create_code(60);
        assert_eq!(state.attempt(&code), PairingOutcome::Ok);
        assert_eq!(state.attempt(&code), PairingOutcome::Invalid);
    }
}
