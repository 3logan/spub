# SPUB

**Open-source Python tools for encrypted, verifiable records on Stellar.**

SPUB is an experimental, open-source Python project exploring how small encrypted records can be preserved, retrieved, and independently verified using the Stellar blockchain.

The long-term goal is to make publishing a small historical note, research observation, or AI agent checkpoint straightforward without requiring users to understand blockchain transactions.

## Current functionality

Version 0.1.0 provides:

- Local AES-256-GCM encryption of UTF-8 text.
- Local decryption and authenticated recovery.
- A compact, versioned binary package format.
- Automatic generation of a random encryption key and nonce.

**Blockchain publication and retrieval are not yet implemented in this package.**

The current library performs its operations locally and does not transmit notes or encryption keys to SPUB.net.

## Example

```python
import spub

# Encrypt a note locally
package, key = spub.encrypt(
    "This is my first encrypted SPUB checkpoint."
)

# Recover the original note
original = spub.decrypt(package, key)

print(original)
```

`package` contains the encrypted binary data.

`key` is the secret 32-byte AES-256 key required to decrypt it. The key is deliberately excluded from the package.

**Keep the key private and preserve it securely. Losing the key means losing access to the original note.**

## SPUB-E v1 binary format

The initial encrypted package uses this layout:

| Component | Size |
|---|---|
| Header (`SPUBE` + version byte `0x01`) | 6 bytes |
| AES-GCM nonce | 12 bytes |
| Ciphertext | Variable |
| Authentication tag | 16 bytes |

Total overhead: **34 bytes** beyond the original UTF-8 plaintext.

The header is authenticated using AES-GCM Additional Authenticated Data (AAD). The encryption key is not stored in the package.

This format is experimental and may change before a stable protocol release.

## Development

Clone the repository and install the development environment using [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

Run the automated tests:

```bash
uv run python -m pytest -v
```

Run the example:

```bash
uv run python examples/basic_encryption.py
```

## Security considerations

SPUB uses the Python `cryptography` library's AES-256-GCM implementation.

This project has not undergone an independent security audit. Its current encryption implementation should be considered experimental.

SPUB does not recover lost encryption keys, and successful encryption does not establish the legality, authenticity, or provenance of the original material.

## Project status

SPUB is in early development. Planned areas of exploration include Stellar publication, transaction receipts, independent recovery, and protocol interoperability.

The intended protocol is open, so independently implemented clients should eventually be able to create and recover compatible publications without depending on SPUB.net.