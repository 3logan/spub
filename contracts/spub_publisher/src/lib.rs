#![no_std]

use soroban_sdk::{contract, contractimpl, Bytes, Env};

/// Test-only contract: takes opaque bytes but writes no contract data.
/// The bytes are passed as arguments in the transaction envelope.
#[contract]
pub struct SpubProbe;

#[contractimpl]
impl SpubProbe {
    pub fn publish(_env: Env, data: Bytes) -> u32 {
        data.len()
    }
}
