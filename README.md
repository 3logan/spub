# SPUB — durable, verifiable short-form publishing on Stellar

**Status: experimental / pre-release.** SPUB1 is being designed and tested. **There is no published canonical Mainnet SPUB1 contract in this repository yet.** Do not use this project for irreplaceable data or assume archival availability or perpetual secrecy.

SPUB aims to make it easy to publish a **short encrypted record** on the Stellar blockchain, receive a public locator, and later recover the original encrypted bytes **without needing spub.net or a proprietary database**.

A SPUB publication is meant to be *small, durable, independently recoverable and verifiable*. SPUB is **not** primarily a secure-messaging product or a managed secrets vault.

## The idea in one minute

1. Prepare an encrypted `.spub` package locally.
2. Preview Stellar network fees and the transaction validity timeout.
3. Authorize **one** Soroban contract invocation containing the complete package.
4. Receive a publication ID and a **private local receipt**.
5. Later retrieve the exact `.spub` bytes from Stellar historical transaction data; decrypt using a separately retained or shared key.

The emerging SPUB1 design uses AES-256-GCM for document encryption and standardized **AES-256 Key Wrap (RFC 3394)** to protect the individual document key with a publisher-controlled master key. The encryption scheme is still a **draft** pending interoperability tests.

## Proposed SPUB1 boundaries

| Property | Current proposal |
|---|---|
| Transport | Soroban transaction argument; one transaction per publication |
| Maximum package | **Less than 25 KiB**, including envelope; pending transaction-size testing |
| Stored content | Historical transaction argument, **not** contract persistent/temporary storage |
| Contract | Public, minimal contract with size/version validation, publisher authorization and metadata event |
| Package file | `.spub` for both prepared and recovered bytes |
| Header candidate | 5-byte `SPUB` + version, 40-byte AES-KW key, 12-byte nonce, 16-byte GCM tag, then ciphertext |
| Identifier | `spub1:<network>:<ledger>:<transaction-hash>` |
| Key custody | Publisher-controlled; no required hosted key database |
| Chunking and large files | Outside SPUB1 |

### Publication ID

```text
spub1:t:5499902:46c026cc0106f8de226df6e76cf6dc995d61a6d05eed346914d63d6bb15c401f
```

This **real historical Testnet probe locator** points to an earlier **80 KiB experiment**, not a finalized SPUB1 publication. `t` means Testnet; `m` will denote Mainnet. A locator is **not a decryption key**.

## Planned usage (illustrative; commands not implemented yet)

```python
import spub

package = spub.prepare("checkpoint.md", save=True)  # optional offline step
quote = spub.estimate(package, network="testnet")
quote.show()
receipt = spub.publish(package, network="testnet")
receipt.show()

# One-step preparation + publication will also be supported:
# receipt = spub.publish("checkpoint.md", network="testnet")
```

A publisher does **not** send a Stellar secret key or AES key to the Soroban contract. The client signs locally; the contract receives the **public publisher address** and encrypted package. Different people can publish or retrieve encrypted packages, and recipients do not need a Stellar wallet simply to decrypt them.

**Receipts stay private.** Local receipt fields may include source filename/path, encryption time, submission/confirmation time, actual fees, transaction hash, ledger and publication ID. Original filenames, local paths and AES keys are not put in the public package or contract events. Stellar still exposes the public publisher address, timing, transaction metadata and encrypted bytes.

## Working evidence — not yet a production guarantee

Earlier `soroban_probe` experiments published an **80 KiB** payload in a Soroban Testnet transaction and recovered the matching bytes from a Stellar History Archive without using contract persistent storage. This was an architectural proof of concept; it did **not** freeze SPUB1's smaller size cap or its revised encryption envelope.

The next milestone is **stronger independent archive verification**: transaction success, invocation/contract identity, transaction/results commitments, ledger hash-chain consistency and—where practical—an independently trusted checkpoint hash.

## Documents

- [SPUB1 protocol specification — draft](docs/SPUB1_PROTOCOL_DRAFT.md): byte layout, security boundaries, contract rules, IDs and retrieval.
- [Python implementation and test plan — draft](docs/PYTHON_IMPLEMENTATION_DRAFT.md): modules, development phases, acceptance tests and a controlled Mainnet test.

## What is deliberately deferred

Large-file chunking, commercial payments, hosted indexing/search, subscriptions, sponsored transactions, browser applications and on-chain document storage. They are not prerequisites for the first working SPUB1 implementation.

## Open development model

The intent is an open protocol, independently implemented. Anyone should be able to build a compatible publisher or reader, and to deploy a copy of the contract's Wasm under another address. The canonical SPUB1 contract addresses will be documented by network once deployed. This does not give spub.net custody of readers' encryption keys.

*Protocol, software and security behavior remain subject to test and revision before release.*
