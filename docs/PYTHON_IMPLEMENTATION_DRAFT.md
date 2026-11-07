# SPUB Python SDK & CLI — Implementation Plan (Draft)

**Date:** 2026-11-07  
**Purpose:** A focused build plan for someone implementing SPUB incrementally. **Start with archive verification, not the final contract.**  
**Status:** Plan, not completed code. APIs and filenames below are proposed.

## 1. What counts as a successful first release?

A user can **prepare** a portable encrypted `.spub` file, **estimate** the fee/timeout, **publish** it through a fixed Soroban contract on Testnet, receive a **private receipt and valid `spub1:t:` ID**, **retrieve** exactly those bytes from a historical archive and **decrypt** them. The same code supports Mainnet via network configuration, with an explicit cost confirmation. Normal archive checks establish transaction **success**, **contract identity** and a clearly stated **archive-verification level**.

Avoid making the initial version solve global indexing, chunking, hosted key backup, payments, or a public web UI.

## 2. Proposed repository layout

```text
spub/
  README.md
  pyproject.toml
  .gitignore
  docs/
    SPUB1_PROTOCOL_DRAFT.md
    PYTHON_IMPLEMENTATION_DRAFT.md
  src/spub/
    __init__.py
    __main__.py
    config.py          # network, contract, local paths, safe defaults
    crypto.py          # AES-256-GCM + RFC 3394 AES-256-KW
    package.py         # parse/build/check binary SPUB1 envelope
    keys.py            # explicit KEK initialization, lookup, backup/export
    stellar.py         # TransactionBuilder + SorobanServer operations
    archive.py         # retrieve and parse checkpoint XDR
    verification.py    # success/contract/commitment/trust-anchor validation
    receipts.py        # private one-receipt JSON format
    cli.py             # installable human + agent interface
  contracts/spub1/     # minimal Rust/Soroban Wasm source
  tests/
    test_package.py
    test_crypto.py
    test_archive.py
    test_transaction.py
    fixtures/          # canonical test-only vectors and historical samples
```

Keep existing `soroban_probe` and working archive reader code as **reference experiments** until their behavior is covered by tests; don't rewrite them all at once.

## 3. Python API — proposed behavior

```python
package = spub.prepare("checkpoint.md", save=True)
quote = spub.estimate(package, network="testnet")
receipt = spub.publish(package, network="testnet", timeout=300)

# Convenience: auto-prepare raw source, preserving the same crypto logic
receipt = spub.publish("checkpoint.md", network="testnet")

# For a pre-existing .spub package, do not re-encrypt it
receipt = spub.publish("checkpoint.md.spub", network="testnet")

raw_package = spub.retrieve(publication_id)
plaintext = spub.decrypt(raw_package, master_key=...)
```

- `prepare`: no network or Stellar signing secret required; may return package object or write `.spub`; capture encryption timestamp **locally**, not inside public bytes.
- `estimate`: uses **the same invocation-building routine as `publish`** and network simulation. Show package bytes, network/contract, estimated resource fee, maximum inclusion bid, maximum total fee, explicit restoration estimate, validity timeout and plausible confirmation range. Estimate isn't a guarantee.
- `publish`: choose Testnet by default during development; **prompt/confirm for Mainnet**. Obtain a signer locally (e.g. secure interactive prompt or configured external signer); sign only after the fee cap is accepted. Submit, wait/poll, and avoid blind retries if outcome is uncertain.
- `retrieve`: no Stellar wallet or AES key; return exact recovered `.spub` bytes and a **verification report**.
- `decrypt`: key unwrap and GCM authenticate; never return plaintext if validation fails.

Existing `.spub` files may come from third parties. The official client can attempt decryption before publishing when the KEK/DEK is available; if a publisher deliberately submits without a key, require a clear `allow_unverified` option. Contract admission remains only structural.

## 4. Core dependencies and implementation policy

- Use `cryptography` for `AESGCM`, `aes_key_wrap` and `aes_key_unwrap`; **do not implement AES manually**.
- Use `stellar-sdk` (Python) and its `TransactionBuilder` plus `SorobanServer` / current higher-level equivalent for simulation, preparation, signing and transaction-status results.
- Use the Stellar RPC client for Soroban; don't use Horizon `Server` with a made-up URL for contract invocation.
- Use an XDR parser provided by the SDK where possible; do not implement an independent Stellar consensus engine just for SPUB.
- Use `platformdirs` for local config/receipt locations. `keyring` should initially be an **optional key-custody backend**, not a required dependency of the SPUB wire format.
- Use a `src/` Python package with a `pyproject.toml`, installable CLI and automated `pytest` tests. Pin tested versions before release; current SDK APIs can evolve.

## 5. The next objective: stronger archive verification

**Do this before writing the final Soroban contract.** It uses the existing working archive-reader prototype and produces reusable tests for both networks.

### Phase A — read-only, low-cost local/archive tests

**A1. Recovery baseline.** Re-run the previously known 80 KiB Testnet `soroban_probe` locator, when Testnet history still contains it. Verify bytes, size, SHA-256 and exact hash/ledger. If Testnet has reset, create a new small Testnet fixture; do not silently switch to a different transaction.

**A2. Transaction-result validation.** From the matching archive **results** XDR, prove that the candidate invocation's transaction result is `SUCCESS`. Confirm the alignment/order of transactions and results; include an intentionally failed Soroban transaction as a negative fixture (or a published archive fixture with documented known failure).

**A3. Invocation inspection.** Check `InvokeHostFunction`/contract-call target, function name and *full* `Bytes` argument. Reject a correct-looking `.spub` package that was not published through the expected contract. For earlier probe fixtures, check the known **probe** contract/function, not SPUB1's future canonical contract.

**A4. Archive internal consistency.** Verify XDR parsing, ledger-header hashes, transaction-set commitments, transaction-result-set commitments, and chain links within and across checkpoints. Prefer testing or invoking **Rust Stellar Archivist** with `scan --verify` rather than re-implementing all of these checks. Precisely state what the tool checked.

**A5. Archive source independence.** Fetch the same Mainnet (read-only) transaction checkpoint from two distinct compatible archives when available. Compare the exact ledger/transaction bytes and verification findings. Agreement is useful evidence, **not by itself consensus proof**.

**A6. Trust anchoring.** Verify a checkpoint/ledger hash against a **separately trusted hash**. Explore the official `stellar-core verify-checkpoints` / trusted checkpoint reference workflow. Report `located`, `archive_verified`, or `consensus_anchored` separately; fail closed on contradictions.

**A7. Edge and corruption tests.** Wrong network passphrase, bad ledger, wrong tx hash, truncated gzip/XDR, tampered archive bytes, checkpoint boundary (`63/64/65`-style), unexpected fee-bump envelope, unknown contract/function, wrong/missing results, and stale/missing archive checkpoint.

**A8. Verification report.** Return a small machine-readable record such as:

```json
{
  "publication_id": "spub1:t:...",
  "network": "testnet",
  "ledger": 12345,
  "transaction_success": true,
  "contract_verified": true,
  "payload_sha256": "...",
  "archive_verification": "archive_verified",
  "trusted_checkpoint": null,
  "archive_source": "configured-history-archive",
  "notes": []
}
```

This JSON is **illustrative**, not a final public schema. Avoid claiming `contract_verified` on the old probe as if it were the new SPUB1 contract.

### Specific acceptance criteria for archive milestone

- A matching historical transaction is recovered and recomputed to the expected network-bound hash.
- Result-file verification distinguishes successful inclusion from on-chain failure.
- A known valid example yields exactly the original argument bytes, while each corruption/negative fixture is rejected with a clear error.
- Reported verification level never exceeds work actually performed.
- Run the same archive verification routines for Testnet and Mainnet using **only configuration changes**.

## 6. Focused Mainnet test ladder — no need to rush a paid publication

**M0 — free, read-only:** choose a known, already-finalized **ordinary Mainnet transaction** with a documented successful Soroban invocation; verify archive checkpoint, network-specific transaction hash, result success and ledger commitment. Since it isn't SPUB1, don't claim canonical-SPUB1 conformance.

**M1 — free, read-only:** retrieve the same checkpoint from two independent archives and compare, then test a separately trusted checkpoint hash. Archive availability and API/RPC provider charges may still apply.

**M2 — controlled paid test, only after deploying and validating SPUB1 contract:** publish a **small, non-sensitive** file (for example, several hundred bytes), using a new or otherwise carefully funded Mainnet account. Simulate the exact transaction first, review the fee maximum and 300-second validity, authorize once, capture receipt, then recover it **from archive history**. A checkpoint may not yet be uploaded immediately after confirmation; record any wait before archive visibility as a separate metric.

**M3 — edge case, optional:** submit a structurally invalid small package on Testnet, not Mainnet, to test expected contract rejection and paid-failure behavior.

Never put a production Stellar signing secret or a real master key in tests, logs, public fixtures, or GitHub.

## 7. Build phases after archive verification

| Phase | Deliverable | Done when |
|---|---|---|
| 1 | Archive verification hardening | A1–A8 pass, including clear trust levels and Mainnet read-only checks |
| 2 | Exact `.spub` codec/crypto | AES-KW/GCM round-trip, fixed vector, tamper failures, package size bounds |
| 3 | Stateless Soroban contract | Valid package accepted; bad prefix/length rejected; publisher auth works; no storage writes |
| 4 | Publish + estimate | Same transaction construction; visible resource/inclusion/restore quote; no silent fee increase |
| 5 | Private receipt + key setup | One final receipt, known/unknown timestamps handled, no secret material in JSON |
| 6 | End-to-end Testnet | One-step prepare/publish/ID/retrieve/decrypt and interrupted-status tests |
| 7 | Controlled Mainnet | M2 published and recovered; costs and limits recorded; docs updated |

## 8. Fee and transaction handling — developer checklist

- Separate Stellar network configuration (passphrase, RPC URL, archive URLs, canonical contract, ID code); **do not** duplicate publisher functions for Testnet versus Mainnet.
- Source account transaction signing happens locally. Don't send `S...` keys to the contract. `spub.prepare()` does not need signing credentials.
- Simulation yields a resource fee estimate and runtime footprints; fees may change between estimate and inclusion. The final prepared transaction must be checked against a user-authorized total fee ceiling.
- Make restoration *opt in when it adds unexpected charges*. If the publisher declines, stop without submitting. Contract instance/Wasm TTL and transaction timeout are unrelated.
- The validity timeout defaults to 300 seconds **as a client preference**, not as a property of the binary package.
- Preserve transaction hash and signed-XDR correlation in **minimal private recovery state** until status is certain. Distinguish failed, expired, successful and unresolved. Never blindly rebroadcast a new transaction on an RPC timeout.
- Capture actual charged fees/any refunds from finalized results rather than showing the simulated amount as actual.

## 9. Master-key management and privacy — still draft

One 32-byte publisher-owned master key (KEK) may reside in the OS credential store through `keyring`; SPUB should also support *explicit* import, backup/export and recovery. **Never silently generate a new master key when an expected key is missing.** The private local receipt may contain source filename/path, encryption time (if known), package mtime, original modified time, date submitted, ledger confirmation time, fee quote and actual charge, but **never the KEK or DEK**.

Sharing an individual document requires the document's DEK and publication ID; sharing a master key potentially opens all packages wrapped by that master key. For the planned public "SPUB specification published using SPUB" example, share **only that document DEK** in GitHub.

## 10. Questions not worth holding up the first test

- Exact config/receipt directories (per publishing collection versus centralized) can be set after archive verification.
- Whether OS credential `keyring` is a default or optional backend can be decided after the crypto layer works.
- Event topics and error-code style can be pinned down when writing the minimal contract.
- Automated quarterly canonical contract TTL renewal is an operations script, not a blocker for archive verification.

## 11. Documentation and primary references

- Stellar Python SDK RPC and transaction preparation: https://stellar-sdk.readthedocs.io/en/latest/api.html
- Archivist archive verification: https://github.com/stellar/rs-stellar-archivist
- Stellar Core checkpoint-hash trust: https://github.com/stellar/stellar-core/blob/master/docs/quick-reference.md
- Protocol 23 Soroban state restoration: https://stellar.org/blog/developers/announcing-protocol-23
- Python `cryptography` AES-GCM and AES-KW: https://cryptography.io/en/stable/hazmat/primitives/

**Next practical action:** Take the existing archive-reader script, put one historical fixture under `tests/fixtures/`, and write **A2 (success-results XDR)** and **A3 (contract-invocation check)** before touching Mainnet signing code. That is the shortest route to a stronger, testable recovery claim.
