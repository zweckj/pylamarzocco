"""Helpers for the pylamarzocco package."""

import base64
import hashlib
import time
import uuid
from dataclasses import dataclass, field

from aiohttp import ClientResponse
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ec import (
    ECDSA,
    SECP256R1,
    EllipticCurvePrivateKey,
    generate_private_key,
)
from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin

from .const import StompMessageType


def is_success(response: ClientResponse) -> bool:
    """Check if response is successful."""
    return 200 <= response.status < 300


def encode_stomp_ws_message(
    msg_type: StompMessageType, headers: dict[str, str], body: str | None = None
) -> str:
    """Encode STOMP WebSocket message."""
    fragments: list[str] = []
    fragments.append(str(msg_type))
    for key, value in headers.items():
        fragments.append(f"{key}:{value}")
    msg = "\n".join(fragments)
    msg += "\n\n"
    if body:
        msg += body
    msg += "\x00"
    return msg


def decode_stomp_ws_message(
    msg: str,
) -> tuple[StompMessageType, dict[str, str], str | None]:
    """Decode STOMP WebSocket message."""
    header, data = msg.split("\n\n", 1)
    headers: dict[str, str] = {}
    metadata = header.split("\n")
    msg_type = StompMessageType(metadata[0])
    for header in metadata[1:]:
        key, value = header.split(":", 1)
        headers[key] = value
    if data.endswith("\x00"):
        data = data[:-1]
    return msg_type, headers, data


def b64(data: bytes) -> str:
    """Base64 encode bytes to ASCII string."""
    return base64.b64encode(data).decode("ascii")


def generate_request_proof(base_string: str, secret32: bytes) -> str:
    """La Marzocco's custom proof generation algorithm (Y5.e equivalent)"""
    if len(secret32) != 32:
        raise ValueError("secret must be 32 bytes")

    work = bytearray(secret32)  # Make mutable copy

    for byte_val in base_string.encode("utf-8"):
        idx = byte_val % 32
        shift_idx = (idx + 1) % 32
        shift_amount = work[shift_idx] & 7  # 0-7 bit shift

        # XOR then rotate left
        xor_result = byte_val ^ work[idx]
        rotated = (
            (xor_result << shift_amount) | (xor_result >> (8 - shift_amount))
        ) & 0xFF
        work[idx] = rotated

    return b64(hashlib.sha256(work).digest())


@dataclass
class SecretData(DataClassJSONMixin):
    """Holds key material derived from installation ID."""

    secret: bytes = field(
        metadata=field_options(serialize=b64, deserialize=base64.b64decode)
    )
    private_key: EllipticCurvePrivateKey = field(
        metadata=field_options(
            serialize=lambda key: b64(
                key.private_bytes(
                    encoding=serialization.Encoding.DER,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            ),
            deserialize=lambda s: serialization.load_der_private_key(
                base64.b64decode(s), password=None
            ),
        )
    )
    installation_id: str

    @property
    def public_key_b64(self) -> str:
        """Return public key in base64-encoded DER format."""
        pub_bytes = self.private_key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return b64(pub_bytes)

    @property
    def base_string(self) -> str:
        """Return base string: installation_id.sha256(public_key_der_bytes)"""
        pub_bytes = self.private_key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        pub_hash_b64 = b64(
            hashlib.sha256(pub_bytes).digest()
        )  # Hash raw bytes, not base64 string
        return f"{self.installation_id}.{pub_hash_b64}"


def generate_extra_request_headers(secret_data: SecretData) -> dict[str, str]:
    """Generate extra headers for normal API calls after authentication"""

    # Generate nonce and timestamp
    nonce = str(uuid.uuid4()).lower()
    timestamp = str(int(time.time() * 1000))  # milliseconds

    # Create proof using Y5.e algorithm: installation_id.nonce.timestamp
    proof_input = f"{secret_data.installation_id}.{nonce}.{timestamp}"
    proof = generate_request_proof(proof_input, secret_data.secret)

    # Create signature data: installation_id.nonce.timestamp.proof
    signature_data = f"{proof_input}.{proof}"

    # Sign with ECDSA
    signature = secret_data.private_key.sign(
        signature_data.encode("utf-8"), ECDSA(hashes.SHA256())
    )
    signature_b64 = b64(signature)

    # Return headers
    return {
        "X-App-Installation-Id": secret_data.installation_id,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
        "X-Request-Signature": signature_b64,
    }


def generate_secret_data(installation_id: str) -> SecretData:
    """Generate the key material from installation ID."""

    def derive_secret_bytes(installation_id: str, pub_der_bytes: bytes) -> bytes:
        pub_b64 = b64(pub_der_bytes)
        inst_hash = hashlib.sha256(installation_id.encode("utf-8")).digest()
        inst_hash_b64 = b64(inst_hash)
        triple = f"{installation_id}.{pub_b64}.{inst_hash_b64}"
        return hashlib.sha256(triple.encode("utf-8")).digest()  # 32 bytes

    private_key = generate_private_key(SECP256R1())

    pub_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )

    secret_bytes = derive_secret_bytes(installation_id, pub_bytes)
    return SecretData(
        installation_id=installation_id, secret=secret_bytes, private_key=private_key
    )
