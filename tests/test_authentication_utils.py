"""Test authentication utility functions."""

import pytest
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key

from pylamarzocco.util import (
    InstallationKey,
    generate_extra_request_headers,
    generate_installation_key,
    generate_request_proof,
)


class TestAuthenticationUtils:
    """Test authentication utility functions."""

    def test_generate_request_proof_valid(self) -> None:
        """Test generate_request_proof with valid inputs."""
        secret = b"0" * 32  # 32 bytes
        base_string = "test.string.123"
        
        result = generate_request_proof(base_string, secret)
        
        # Should return a base64 encoded string
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Should be deterministic
        result2 = generate_request_proof(base_string, secret)
        assert result == result2

    def test_generate_request_proof_invalid_secret_length(self) -> None:
        """Test generate_request_proof with invalid secret length."""
        secret_too_short = b"0" * 31
        secret_too_long = b"0" * 33
        base_string = "test.string"
        
        with pytest.raises(ValueError, match="secret must be 32 bytes"):
            generate_request_proof(base_string, secret_too_short)
            
        with pytest.raises(ValueError, match="secret must be 32 bytes"):
            generate_request_proof(base_string, secret_too_long)

    def test_generate_request_proof_different_inputs(self) -> None:
        """Test generate_request_proof with different inputs produce different results."""
        secret = b"1" * 32
        
        result1 = generate_request_proof("string1", secret)
        result2 = generate_request_proof("string2", secret)
        
        assert result1 != result2

    def test_generate_request_proof_empty_string(self) -> None:
        """Test generate_request_proof with empty base string."""
        secret = b"2" * 32
        
        result = generate_request_proof("", secret)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_request_proof_unicode_string(self) -> None:
        """Test generate_request_proof with unicode characters."""
        secret = b"3" * 32
        
        result = generate_request_proof("test.üñíçødé.123", secret)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_installation_key(self) -> None:
        """Test generate_installation_key function."""
        installation_id = "test-installation-id"
        
        key = generate_installation_key(installation_id)
        
        assert isinstance(key, InstallationKey)
        assert key.installation_id == installation_id
        assert len(key.secret) == 32
        assert key.private_key is not None
        
        # Should generate different keys for different installation IDs
        key2 = generate_installation_key("different-id")
        assert key.secret != key2.secret
        assert key.installation_id != key2.installation_id

    def test_installation_key_properties(self) -> None:
        """Test InstallationKey properties."""
        key = generate_installation_key("test-id")
        
        # Test public_key_b64 property
        pub_key_b64 = key.public_key_b64
        assert isinstance(pub_key_b64, str)
        assert len(pub_key_b64) > 0
        
        # Test base_string property
        base_string = key.base_string  
        assert isinstance(base_string, str)
        assert base_string.startswith("test-id.")
        assert "." in base_string

    def test_installation_key_serialization(self) -> None:
        """Test InstallationKey JSON serialization and deserialization."""
        original_key = generate_installation_key("test-serialization")
        
        # Serialize to dict
        serialized = original_key.to_dict()
        assert isinstance(serialized, dict)
        assert "secret" in serialized
        assert "private_key" in serialized 
        assert "installation_id" in serialized
        
        # Deserialize back
        deserialized_key = InstallationKey.from_dict(serialized)
        
        # Should be equivalent
        assert deserialized_key.installation_id == original_key.installation_id
        assert deserialized_key.secret == original_key.secret
        assert deserialized_key.public_key_b64 == original_key.public_key_b64

    def test_generate_extra_request_headers(self) -> None:
        """Test generate_extra_request_headers function."""
        key = generate_installation_key("test-headers")
        
        headers = generate_extra_request_headers(key)
        
        assert isinstance(headers, dict)
        assert "X-App-Installation-Id" in headers
        assert "X-Timestamp" in headers  
        assert "X-Nonce" in headers
        assert "X-Request-Signature" in headers
        
        assert headers["X-App-Installation-Id"] == key.installation_id
        assert headers["X-Timestamp"].isdigit()
        assert len(headers["X-Nonce"]) > 0
        assert len(headers["X-Request-Signature"]) > 0
        
        # Should generate different headers on subsequent calls
        headers2 = generate_extra_request_headers(key)
        assert headers["X-Timestamp"] != headers2["X-Timestamp"] or headers["X-Nonce"] != headers2["X-Nonce"]

    def test_generate_extra_request_headers_consistency(self) -> None:
        """Test that headers are consistent for same key."""
        key = generate_installation_key("test-consistency")
        
        headers1 = generate_extra_request_headers(key)
        headers2 = generate_extra_request_headers(key)
        
        # Installation ID should be the same
        assert headers1["X-App-Installation-Id"] == headers2["X-App-Installation-Id"]
        
        # But nonce and timestamp should be different
        assert headers1["X-Nonce"] != headers2["X-Nonce"]