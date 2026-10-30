import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


HEADER = b"SPUBE\x01"
NONCE_SIZE = 12
TAG_SIZE = 16


def encrypt(text: str) -> tuple[bytes, bytes]:
    """
    Encrypt a UTF-8 note using AES-256-GCM.

    Returns:
        package: Versioned encrypted binary package.
        key:     Secret 32-byte AES key. Keep private.
    """

    plaintext = text.encode("utf-8")

    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(NONCE_SIZE)

    aesgcm = AESGCM(key)

    ciphertext = aesgcm.encrypt(
        nonce,
        plaintext,
        HEADER,
    )

    package = HEADER + nonce + ciphertext

    return package, key


def decrypt(package: bytes, key: bytes) -> str:
    """
    Decrypt a SPUB-E v1 package and return its UTF-8 text.

    Raises ValueError for an unsupported or truncated package.
    Raises InvalidTag if authentication fails.
    """

    minimum_size = len(HEADER) + NONCE_SIZE + TAG_SIZE

    if len(package) < minimum_size:
        raise ValueError("Invalid SPUB-E package length")

    if not package.startswith(HEADER):
        raise ValueError("Unsupported SPUB-E package format")

    nonce_start = len(HEADER)
    nonce_end = nonce_start + NONCE_SIZE

    nonce = package[nonce_start:nonce_end]
    ciphertext = package[nonce_end:]

    aesgcm = AESGCM(key)

    plaintext = aesgcm.decrypt(
        nonce,
        ciphertext,
        HEADER,
    )

    return plaintext.decode("utf-8")