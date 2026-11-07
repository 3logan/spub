# SPUB1 Protocol Specification — Draft 0.2

**Date:** 2026-11-07  
**Status:** Working proposal for implementation and testing; **not a released standard**  
**Scope:** Single-transaction Soroban publication of short encrypted records on Stellar

> This document intentionally distinguishes **selected design directions**, **candidate byte-level rules**, and **decisions still open**. Implementations built for testing may change before SPUB1 is frozen. Nothing here identifies a live canonical Mainnet contract.

## 1. Purpose and trust model

SPUB1 is a proposed open protocol for publishing a short binary record as an argument to a Soroban contract invocation. Its objectives are:

- A durable, independently locatable record in Stellar's historical transactions.
- Exact-byte integrity and publisher authorization verifiable without trusting spub.net.
- A compact, portable encrypted `.spub` package whose decryption keys are controlled by its publisher or reader.
- Low operational complexity: **one package, one invocation, one transaction, one publication identifier**.

SPUB1 does **not** promise that a specific history archive operator will retain data forever, that ciphertext will remain secret after a key is disclosed, or that the contract can prove that supplied bytes were genuinely encrypted. The authenticated **publisher** is the address authorizing a transaction, not necessarily the document's author or encryptor.

The format, contract, and independent reader are publicly implementable. spub.net is optional.

## 2. Publication scope — selected direction

- A publication is the complete `.spub` binary package passed as **one Soroban `Bytes` argument** to a designated `publish` contract function.
- Encoded package size **MUST be < 25 KiB**, i.e. `len(package) < 25_600` bytes. This is a *proposed SPUB1 protocol cap*, not a claim about the largest valid Stellar transaction; actual signed-XDR and network-resource margins **MUST be tested**.
- No protocol chunking, multi-transaction manifests, contract-managed upload queues, or large-file storage in SPUB1.
- The package is retained in **historical transaction arguments**, not written to temporary or persistent Soroban contract storage. Transient execution memory is not a ledger-storage entry.
- Each confirmed successful publication receives exactly one network/ledger/transaction-hash locator.
- Larger files, commercial convenience services, and additional content types/versions are out of scope.

## 3. Proposed `.spub` wire format — candidate to freeze after tests

**This 73-byte envelope is the leading AES-KW/AES-GCM candidate, superseding the earlier 33-byte no-key-wrap draft.** All offsets below are **zero-based, start inclusive, end exclusive**. Values are raw binary, not printable hexadecimal or Base64 text.

| Field | Offset `[start,end)` | Bytes | Meaning |
|---|---:|---:|---|
| Magic | `[0,4)` | 4 | ASCII `SPUB` (`53 50 55 42`) |
| Version | `[4,5)` | 1 | `0x01` |
| Wrapped document key | `[5,45)` | 40 | RFC 3394 AES-256-KW wrapping of one 32-byte document key |
| Document nonce | `[45,57)` | 12 | 96-bit nonce for document AES-GCM |
| Document authentication tag | `[57,73)` | 16 | 128-bit GCM authentication tag |
| Document ciphertext | `[73,end)` | variable | AES-GCM encrypted original bytes |

In compact form:

```text
SPUB | 01 | wrapped_dek[40] | nonce[12] | tag[16] | ciphertext[*]
```

- Fixed overhead: **73 bytes**.
- Maximum original uncompressed plaintext under the proposed strict package cap: **25,526 bytes** (`25,599 - 73`), assuming no other in-package metadata.
- Version `0x00` is **reserved** for possible plaintext publication and **MUST be rejected by SPUB1**. Versions other than `0x01` are rejected.
- `.spub` is the filename extension for *both* prepared and archive-retrieved packages. The extension and local filename are not authoritative; the binary header is.
- Original names, paths, content type, creation time, recipient/folder identity and encryption timestamps are **not** included in the public package.
- A 73-byte package containing empty plaintext is technically valid AES-GCM; whether SPUB1 permits empty documents remains **OPEN**. A first implementation may reject empty documents as an explicitly documented pre-release policy.

### 3.1 Encryption — proposed interoperable algorithm

1. Obtain a 32-byte **master key** (key-encryption key, KEK), controlled by the publisher. The key is not transmitted to Stellar.
2. Generate a fresh **32-byte document encryption key** (DEK) using a cryptographically secure random generator.
3. Compute `wrapped_dek = AES-KW-RFC3394(kek, dek)`. The output MUST be exactly 40 bytes; use standard **AES Key Wrap, without padding**, and a 256-bit KEK.
4. Generate a fresh random 12-byte document nonce. Since DEKs are independently generated per publication, key/nonce reuse is already strongly disfavored; uniqueness remains required.
5. Construct AAD as the **exact first 57 package bytes**:

   ```python
   aad = b"SPUB\x01" + wrapped_dek + nonce
   ```

6. Run `AES-256-GCM(dek).encrypt(nonce, plaintext, aad)`. The Python `cryptography` API returns `ciphertext || 16-byte-tag`. Serialize its final 16 bytes as `tag` at offsets `[57,73)`, followed by `ciphertext` at offset 73.
7. The full package MUST satisfy the size cap before signing.

**Important:** AAD binding above is a **specific design proposal for interoperability**; it was not present in the earlier working `soroban_probe` publication. It should be frozen only after round-trip and independently implemented test vectors pass.

### 3.2 Decryption

- Parse and validate format/length first.
- Either (a) unwrap the 40-byte wrapped DEK with the master key, or (b) supply an individual 32-byte DEK directly, e.g. when a publisher shares access to one publication.
- Reconstruct `aad = package[0:57]` and `ciphertext_and_tag = package[73:] + package[57:73]`.
- Decrypt with `AESGCM(dek).decrypt(package[45:57], ciphertext_and_tag, aad)`.
- On an invalid wrapping key, malformed key or GCM tag failure, report failure and **do not output unauthenticated plaintext**.
- Anyone with a master key can potentially unwrap **all** publications made under that master key. Individual DEK sharing does not disclose the master key.

### 3.3 What envelope validation does and does not mean

The contract can verify size, magic, version, and authorization. It cannot independently authenticate the wrapped key, validate the GCM tag, or establish that meaningful plaintext was encrypted without an appropriate secret. A reader with a valid key can test cryptographic decryptability.

## 4. Publishing contract — candidate interface

The canonical contract is proposed to be deliberately minimal and **stateless with respect to publications**:

```rust
// Illustrative interface only; exact implementation and events are not final.
pub fn publish(env: Env, publisher: Address, package: Bytes) {
    publisher.require_auth();
    // 73 <= package.len() < 25_600 (subject to empty-document decision)
    // package[0..5] == b"SPUB\x01"
    // compute SHA-256(package)
    // emit a publication event
    // no env.storage().temporary().set(...) or persistent().set(...)
}
```

The full package MUST be a contract invocation argument; publishing **only the header** is not SPUB1. The contract MUST NOT accept AES keys in plaintext or require a key to decrypt the document. It MUST NOT maintain a shared on-chain publication counter or upload queue.

**Candidate published event** (schema **OPEN**): event name `published`; topics including the publisher and protocol version; data including the complete package SHA-256 and length. Event-only metadata is public, and events incur resource fees; avoid filenames, directories, recipients and encryption keys. Exact SDK event types/topics and indexing semantics need a fixture test.

The contract's **instance and Wasm** still have TTLs even without publication storage. Keeping them live may require TTL extension; archived entries can require restoration and extra fees. This does not determine whether *old published bytes* remain in history. The Python client MUST disclose extra restoration costs before signing, and permit the user to decline publication.

### 4.1 Canonical contracts and replicability

- Network `t`: **Testnet** canonical C-address — **TBD**.
- Network `m`: **Mainnet** canonical C-address — **TBD**.
- Contract source, version/revision, and Wasm hash should be public.
- Another party can instantiate the same uploaded Wasm under a separate C-address; it is an independent deployment, **not automatically the canonical contract**.
- Whether canonical SPUB1 is immutable, and the policy for security fixes, remain **OPEN**. Prefer a small, auditable contract and a new protocol version for incompatible changes.

## 5. Publisher authorization and Stellar transaction

The publisher is a Stellar address, supplied as an `Address` argument, and authorizes the complete invocation including the package. For a normal single-source-account publication, the source account signs the transaction **locally** and the Soroban contract calls `publisher.require_auth()`. Network signers/authorization must be verified according to Stellar's actual authorization rules.

- No Stellar `S...` signing secret, master AES key, or unwrapped DEK goes into contract arguments, receipts, or blockchain events.
- Transaction validity timeout (initial client default: **300 seconds**) is **not** the contract-instance TTL.
- Fee auction and admission are controlled by Stellar, not the SPUB contract.
- Standard single-signer, non-fee-bump transactions are the **initial implementation profile**. Future fee bump and sponsored-source transactions require additional ID/auth rules and tests.
- Contract invocation XDR, account authorization, fees and resource limits need actual Testnet tests and limited Mainnet verification before a production claim.

## 6. Public publication identifier — retain prototype convention

```text
spub1:<network>:<decimal-ledger>:<64-lowercase-hex-transaction-hash>
```

- `t` = Testnet; `m` = Mainnet.
- Example from an **earlier 80 KiB Testnet probe, NOT a compliant SPUB1 package**:

  ```text
  spub1:t:5499902:46c026cc0106f8de226df6e76cf6dc995d61a6d05eed346914d63d6bb15c401f
  ```

- The ID is a **locator**, not an encryption key, a fingerprint of plaintext, or a statement about successful decryption.
- The transaction hash is a cryptographic digest and will not visually begin with `SPUB1`. The `spub1:` prefix supplies that namespace.
- Assign an ID **only after verified successful inclusion**, once the actual ledger sequence is known. Repeated publications of identical bytes have distinct transaction IDs.
- The network-specific canonical contract and actual invocation must be checked during recovery; a matching hash alone is insufficient for a canonical SPUB1 claim.

## 7. Independent historical recovery and verification

Given an ID:

1. Parse and strictly validate network, positive decimal ledger and **64-character** lowercase hexadecimal transaction hash.
2. Select the corresponding Stellar network passphrase and configured history-archive source. Never choose a network based solely on an untrusted endpoint URL.
3. Compute the 64-ledger archive checkpoint: `checkpoint = (ledger // 64) * 64 + 63`.
4. Download and decode the corresponding framed-XDR **transactions** checkpoint; locate the transaction in the requested ledger, recomputing its **network-bound transaction hash** from its envelope.
5. Obtain the matching **transaction results** and ledger/header data; validate the transaction actually **succeeded**, not merely appeared in a transaction file.
6. Verify that the successful transaction called the canonical SPUB contract's expected `publish` function, has the expected publisher authorization, and passed the *complete* package as an argument. Reject ambiguous multiple invocations and unsupported fee-bump envelopes in the initial profile.
7. Verify the package header and length; optionally compare its SHA-256 with an independently retained local receipt.
8. Verify archive integrity: checkpoint completeness, transactions/results commitment against ledger headers, ledger-hash continuity and, for stronger provenance, the chain up to an **independently trusted consensus/checkpoint hash**.
9. Return the **exact recovered bytes** as `.spub`; decrypt only if the caller provides an appropriate key.

**Verification level MUST be explicit**. Suggested terms:

- `located`: matching transaction and extracted bytes; not fully authenticated chain history.
- `archive_verified`: internally consistent archive headers, results, transaction commitments and hash links.
- `consensus_anchored`: archive verification additionally linked to a separately trusted checkpoint/consensus hash.

A tool must **not** label arbitrary downloaded archive XDR "consensus verified" merely because it parsed correctly or matched its own computed hash. The Rust Stellar Archivist supports substantial internal archive verification; `stellar-core verify-checkpoints` can produce trusted checkpoint-hash references from a configured consensus trust model. See references.

Old transactions may not be available from ordinary RPC due to retention; the intended long-term path is history archives. Testnet may reset; Mainnet archival claims still depend on the continuing availability of legitimate history data.

## 8. Encryption key custody — probable implementation, NOT wire protocol

The current leading implementation design is **one publisher-controlled master KEK**; every new publication receives a fresh random DEK which is wrapped into its `.spub` header. This removes any required database mapping publications to individual encryption keys.

- SPUB may use the OS credential store through optional Python `keyring`, but long-term key backup/export remains the publisher's responsibility.
- Initialize a new master key **only in an explicit setup operation**; never auto-create a replacement when lookup fails during an attempt to decrypt or publish.
- Provide deliberate export/backup of the master key and export of **individual DEKs** to share selected publications. Never publish a master key as a public "example" if it protects other private publications.
- For a publicly readable sample document, it is acceptable to publish **that document's DEK** alongside its publication ID, making decryption intentionally public.
- Master-key rotation cannot retroactively change immutable existing envelopes; a key compromise exposes all old publications under that master key to anyone who obtains the ciphertext.
- No user key, original filename, path, private hash, local timestamps or key-store identifier is written on-chain.

## 9. Publishing UX, fees and local receipts — implementation requirements

A third-party implementation need not use the Python API, but the official Python client is proposed to support:

```python
package = spub.prepare("document.md", save=True)  # offline; optional
quote   = spub.estimate(package, network="testnet")
receipt = spub.publish(package, network="testnet", timeout=300)
# or spub.publish("document.md", network="testnet")
```

- `estimate` previews bytes, contract/network, estimated resource fee, maximum inclusion bid, maximum total possible fee, timeout, estimated confirmation window and **additional restoration costs if any**. Time is an estimate, not a guarantee.
- `publish` signs locally using a configured signer or explicit interactive prompt. `prepare` requires no Stellar signing secret.
- A package prepared by an independent client may be published. The official client should verify cryptographic decryptability when a key is available; explicit **unverified** submission mode may be allowed with a warning.
- Never silently exceed an explicitly authorized max fee. Retry only after resolving uncertain status, and never confuse an RPC timeout with confirmed chain expiration.
- One **private local JSON receipt** per finished publishing attempt, including status, publication ID (success only), network, G/C addresses, TX hash, ledger, source filename/path (if known), source mtime, preparation/encryption time (if known), submitted/confirmed/receipt timestamps, package mtime, size and hash, quoted and charged fees, timeout, and elapsed time.
- Use ISO 8601 UTC. The receipt **MUST NOT** contain secret keys or get posted to the chain. Local source-path metadata is sensitive: receipts should default to private storage.

The exact JSON schema and default credential-storage mechanism are still **OPEN**.

## 10. Candidate deterministic interoperability vector (test-only)

**This is a candidate vector generated for the draft layout in §3, not a released normative vector. NEVER use these fixed test keys or nonce for live publications.** It was generated locally using Python `cryptography` and round-trip decrypted successfully.

```text
master_KEK_hex:
000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
DEK_hex:
202122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f
nonce_hex:
404142434445464748494a4b
plaintext_utf8:
SPUB1 interoperability test\n
wrapped_DEK_hex:
04f8a3c3c302d3b0b7e94b14dcf85ad1da69cd74056ed7907d3cb49fb27799a4104db058f2901adb
GCM_tag_hex:
1680e9e783cb56160a408cbaf8dcb13a
ciphertext_hex:
9104e8c36156ac6526572247f52f231371e7f1ea813987aa0b8de00a
package_length: 101
package_sha256:
bf0dc1e723bcdc045059223366f2c634ecb8cd289913bb24eb6212a8507dba25
```

Implementation tests MUST reject an altered header, wrapped key, nonce, tag or ciphertext when validating with the appropriate key. A Rust or JavaScript implementation should reproduce these values before the wire format is finalized.

## 11. Open choices before freezing SPUB1

1. Finalize the §3 layout, AAD bytes, and whether empty documents are valid.
2. Lock contract input ABI, event schema, error codes, canonical addresses, and upgrade policy.
3. Verify precise transaction/XDR overhead for a 25 KiB-ish package on current Testnet and then a deliberately small Mainnet sample; lower the cap if network margins require it.
4. Define master-key initialization, export/recovery, and whether credential-store support is a default or an opt-in.
5. Freeze receipt JSON schema and rules for local prepared versus recovered filenames.
6. Implement archive verification with explicit levels and trusted-anchor handling; validate normal success/failure and fee-bump identification.
7. Test restoration/TTL-extension costs and enforce explicit publisher approval for unexpected restoration charges.

## 12. Implementation-neutral references

- Stellar Python SDK: https://stellar-sdk.readthedocs.io/en/latest/
- Stellar Archivist and `--verify`: https://github.com/stellar/rs-stellar-archivist
- Stellar Core checkpoint verification: https://github.com/stellar/stellar-core/blob/master/docs/quick-reference.md
- Stellar Protocol 23 / restoration: https://stellar.org/blog/developers/announcing-protocol-23
- AES-GCM library behavior: https://cryptography.io/en/stable/hazmat/primitives/aead/
- AES Key Wrap (RFC 3394): https://www.rfc-editor.org/rfc/rfc3394
- Python `cryptography` AES-KW: https://cryptography.io/en/stable/hazmat/primitives/keywrap/
