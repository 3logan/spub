# SPUB Python SDK & CLI — Simplified Implementation Plan (Draft 0.3)

**Updated:** 2026-11-07  
**Status:** Proposed implementation, not a released API.  
**Build priority:** Validate historical archive recovery first; then complete prepare → publish → retrieve → decrypt.

## 1. Core model

| Term | Definition |
|---|---|
| **Document** | Original content before encryption |
| **Package** | One immutable encrypted `.spub` byte sequence, identified by SHA-256 |
| **Package record** | Local folder containing that package and its evolving receipt |
| **Publication** | One *successful* Stellar transaction containing the package, with its own publication ID |

**One package can have zero, one, or many publications and failed transaction attempts.** Re-encrypting the same document creates a different package because each preparation uses a fresh document key and nonce. A separate master encryption key (MEK) can be chosen for each intended audience.

There is **one local receipt per package**, not one per transaction, and no mandatory database or ZIP bundle.

## 2. Files and identifiers

Use `platformdirs` for the local application data directory. For example:

```text
<spub-data>/
  packages/
    <64-character-package-sha256>/
      package.spub       # original immutable encrypted bytes
      receipt.json       # evolving local history
    <another-package-sha256>/
      package.spub
      receipt.json
  publications.jsonl     # rebuildable index of successful publications
```

- The folder name is SHA-256 of the **complete `package.spub` bytes**. Verify before trusting a file.
- Importing or retrieving identical encrypted bytes reuses the existing package record. Never silently replace different bytes or lose receipt history.
- Archive retrieval normally **verifies the existing `package.spub`**; it does not create `retrieved.spub`. If the local package is missing, restore the original bytes after validation.
- Source files remain where they are. Private filenames, paths, MEK aliases and local timestamps never go on-chain.

## 3. One evolving `receipt.json`

Create the receipt at preparation/import. Update it as transactions are built, submitted, confirmed, and later retrieved or verified. Its core structure is:

```json
{
  "receipt_version": 1,
  "package_sha256": "<sha256>",
  "source": {"filename": "research.md"},
  "encryption": {"mek_id": "<random-uuid>", "mek_alias": "friend_a"},
  "transactions": [
    {
      "network": "testnet", "hash": "<tx-A>",
      "status": "FAILED", "ledger": 12345,
      "fee_paid_stroops": 180000
    },
    {
      "network": "testnet", "hash": "<tx-B>",
      "status": "SUCCESS", "ledger": 12347,
      "publication_id": "spub1:t:12347:<tx-B>",
      "fee_paid_stroops": 175000,
      "verification_history": []
    }
  ]
}
```

*Illustrative only; hashes/IDs and numerical values are placeholders.* The actual schema also records relevant UTC dates, fee quotes and caps, publisher/contract addresses, expiration and failure diagnostics where known. Unknown private metadata remains absent or null.

Rules:

1. **One attempt per `(network, transaction_hash)`**, updated in place. The transaction hash can be computed **after Soroban transaction preparation and before submission**; persist the attempt before broadcasting. Rebuilding a transaction gives it a new hash.
2. `PENDING` is not success; timeout is **not** proof of failure. Reconcile uncertain attempts before resubmitting. Include confirmed failed transactions and their actual fees.
3. Allow **multiple successful publications** in the same `transactions` array. Keep their distinct publication IDs and **verification histories per transaction**; no single top-level publication ID.
4. Save receipts atomically, with concurrency protection. Preflight errors with no constructed transaction are optional local diagnostics, not blockchain attempts.
5. Never store MEKs, document keys, or Stellar signing secrets in receipts. Receipts are private records, **not independent cryptographic proof**.

## 4. Derived `publications.jsonl`

One JSONL line per **confirmed successful publication**, with `publication_id`, `package_sha256`, network, ledger, transaction hash, and confirmed time. Multiple entries may point to one package record.

- **Normal path:** update `receipt.json` first, then append the success to the index, deduplicating by `(network, transaction_hash)`.
- **Repair path:** `spub publications rebuild` scans `packages/*/receipt.json`, collects successes, and atomically regenerates the index.
- The index is a convenience, not the source of truth. No scheduled scanner, SQL database, or second failure-receipt directory is necessary.

## 5. Multiple master keys, unchanged `.spub` format

Allow any number of MEKs: `personal`, `friend_a`, `friend_b`, etc. Each 32-byte MEK gets a random stable **`mek_id`** plus an optional renameable alias. Keep that identification **locally in `receipt.json`**, never in the public package.

Each `prepare()` generates a new 32-byte document-encryption key (DEK), wraps it with **AES-256-KW (RFC 3394)** and encrypts the plaintext with **AES-256-GCM**. Continue using the proposed **73-byte header**, `SPUB\x01 | wrapped_dek[40] | nonce[12] | tag[16] | ciphertext`, strictly **under 25,600 bytes total**. The protocol draft specifies the candidate offsets and AAD; test and freeze them before release.

Provide explicit `keys create|list|export|import`, optionally backed by OS `keyring`. **Never silently generate a replacement for a missing MEK.** If a retrieved package has no local receipt/MEK association, try a user-selected MEK or available local keys; successful decryption can identify a usable key. Sharing a MEK opens its collection; sharing only a document DEK opens that document.

## 6. Public Python API and CLI

```python
record = spub.prepare("research.md", mek="friend_a")
quote = spub.estimate(record, network="testnet")
receipt = spub.publish(record, network="testnet", timeout=300)

recovered = spub.retrieve(publication_id)   # exact .spub bytes + verification
plain = spub.decrypt(recovered.package, mek="friend_a")
```

`prepare` can also **import** an existing `.spub` without re-encrypting. `publish` accepts an existing record or package ID; a raw-file convenience form can call `prepare` first. `retrieve` may save or reconcile a package record and update the matching receipt. Give AI agents structured Python return values, not just text printed by the CLI.

Initial CLI: `spub keys ...`, `spub prepare`, `spub estimate`, `spub publish`, `spub retrieve`, `spub packages list|show`, and `spub publications list|rebuild`.

## 7. Minimal module layout

```text
src/spub/
  __init__.py, __main__.py
  config.py          # networks, contract IDs, local paths
  crypto.py          # AES-GCM and AES-KW
  package.py         # envelope and content-addressed package records
  keys.py            # multiple MEKs, safe backup/lookup
  stellar.py         # build/simulate/sign/submit/check transaction
  archive.py         # historical retrieval and verification report
  receipts.py        # one evolving JSON receipt per package
  publications.py    # append/rebuild success index
  cli.py
contracts/spub1/     # minimal stateless Soroban contract
 tests/               # interoperable vectors, XDR fixtures and integration tests
```

Use `cryptography`, `stellar-sdk`, `platformdirs`, `pytest`, and optional `keyring`. Split archive verification into another module only if needed. Keep the working `soroban_probe` and archive reader as reference tests, not production dependencies.

## 8. Build order

| Phase | Deliverable and test |
|---|---|
| **1. Archive verification first** | Extend existing reader to validate network-bound transaction hash, **results XDR success**, correct contract/function/full argument, archive commitments/chain links and separately trusted checkpoints where supported. Reject corrupted fixtures and report actual verification level. |
| **2. Local package layer** | Implement SPUB1 codec/crypto, multiple MEKs, hash-named records, evolving receipts and rebuildable index. Round-trip vectors pass; tampered ciphertext fails; re-importing identical bytes deduplicates. |
| **3. Publish on Testnet** | Implement minimal authorized contract and fee simulation. Save hash before submission; record failures, unknowns and multiple successes; index only successes. |
| **4. Retrieve and reconcile** | Recover exact package bytes from archive. Verify transaction success/contract/bytes; update per-publication verification history or reconstruct a record on a new computer. |
| **5. Controlled Mainnet validation** | Run read-only archive tests first; then one small explicitly authorized paid publication with verified fees and archival recovery. |

Preserve meaningful archive levels: **`located`**, **`archive_verified`**, **`consensus_anchored`**. A parsed XDR or local hash match does not by itself establish consensus anchoring.

## 9. Safety and scope

- `estimate()` and `publish()` must use the same transaction-building logic; disclose fee bids, Soroban resource/restoration costs and maximum authorization before signing. Do not silently increase approved fees.
- Require explicit approval for Mainnet. Never treat RPC timeout as a failed chain transaction or blindly publish twice. On-chain failure can still incur fees.
- The contract checks publisher authorization, magic/version/length and emits minimal event metadata. The **entire `.spub` payload is an invocation argument**, not a contract-storage entry. Network contract TTL and transaction timeout are separate concerns.
- Receipts/indexes are **rebuildable local conveniences**: independent archive recovery and decryption must remain possible without them.
- **Defer:** ZIP bundles, SQL/global indexes, background schedulers, hosted services, chunked files, payments, sophisticated search, mandatory keyring, fee-bumps and contract TTL automation.

**Next concrete task:** Add transaction-result checking and contract-invocation checks to the existing archive reader. Then test hash-named package records and evolving receipts before wiring up publishing.

**Documentation follow-up:** The older SPUB1 protocol draft still discusses one MEK and a finished receipt per transaction. Update those *implementation notes* separately; the proposed **73-byte on-chain format does not change**.
