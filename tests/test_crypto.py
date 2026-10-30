import pytest

import spub

from cryptography.exceptions import InvalidTag


def test_round_trip():
    original = "My first SPUB note."

    package, key = spub.encrypt(original)
    recovered = spub.decrypt(package, key)

    assert recovered == original


def test_unicode():
    original = "Hello 🌎 — SPUB is working!"

    package, key = spub.encrypt(original)

    assert spub.decrypt(package, key) == original


def test_wrong_key():
    package, key = spub.encrypt("Secret note")

    _, wrong_key = spub.encrypt("Another note")

    with pytest.raises(InvalidTag):
        spub.decrypt(package, wrong_key)


def test_tampering():
    package, key = spub.encrypt("Important note")

    corrupted = bytearray(package)
    corrupted[-1] ^= 1

    with pytest.raises(InvalidTag):
        spub.decrypt(bytes(corrupted), key)


def test_unique_encryptions():
    package1, key1 = spub.encrypt("Same note")
    package2, key2 = spub.encrypt("Same note")

    assert package1 != package2
    assert key1 != key2