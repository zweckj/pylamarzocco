"""Test the authentication utilities."""

import base64
import hashlib

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ec import ECDSA

from pylamarzocco.util import (
    InstallationKey,
    generate_extra_request_headers,
    generate_installation_key,
    generate_request_proof,
)


def test_generate_installation_key() -> None:
    """Test generating the installation key material."""
    key = generate_installation_key("mock-installation-id")
    assert key.installation_id == "mock-installation-id"
    assert len(key.secret) == 32

    pub_der = base64.b64decode(key.public_key_b64)
    assert pub_der == key.private_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )

    pub_hash = base64.b64encode(hashlib.sha256(pub_der).digest()).decode("ascii")
    assert key.base_string == f"mock-installation-id.{pub_hash}"


def test_installation_key_roundtrip() -> None:
    """Test serializing and deserializing the installation key."""
    key = generate_installation_key("mock-installation-id")
    restored = InstallationKey.from_json(key.to_json())
    assert restored.installation_id == key.installation_id
    assert restored.secret == key.secret
    assert restored.public_key_b64 == key.public_key_b64


def test_generate_request_proof() -> None:
    """Test the request proof is deterministic."""
    proof = generate_request_proof("base-string", bytes(32))
    assert proof == generate_request_proof("base-string", bytes(32))
    assert proof != generate_request_proof("other-string", bytes(32))
    assert len(base64.b64decode(proof)) == 32


def test_generate_request_proof_invalid_secret() -> None:
    """Test the request proof requires a 32 byte secret."""
    with pytest.raises(ValueError, match="secret must be 32 bytes"):
        generate_request_proof("base-string", bytes(16))


def test_generate_extra_request_headers() -> None:
    """Test the extra request headers carry a valid signature."""
    key = generate_installation_key("mock-installation-id")
    headers = generate_extra_request_headers(key)

    assert headers["X-App-Installation-Id"] == "mock-installation-id"
    proof_input = (
        f"mock-installation-id.{headers['X-Nonce']}.{headers['X-Timestamp']}"
    )
    proof = generate_request_proof(proof_input, key.secret)
    # raises InvalidSignature if the signature does not match
    key.private_key.public_key().verify(
        base64.b64decode(headers["X-Request-Signature"]),
        f"{proof_input}.{proof}".encode("utf-8"),
        ECDSA(hashes.SHA256()),
    )
