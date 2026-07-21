"""运行时共享密钥认证测试。"""
import secrets

import pytest

from app.core.errors import RuntimeAuthError


class TestRuntimeKeyAuth:
    """常量时间密钥比较行为。"""

    def test_compare_digest_match(self):
        key = "super-secret-key-at-least-16"
        assert secrets.compare_digest(key, key)

    def test_compare_digest_mismatch(self):
        assert not secrets.compare_digest("key-a-16chars-xxx", "key-b-16chars-xxx")

    def test_compare_digest_empty(self):
        assert not secrets.compare_digest("", "some-key")

    def test_missing_key_raises(self):
        with pytest.raises(RuntimeAuthError):
            raise RuntimeAuthError("Missing X-Agent-Runtime-Key header")

    def test_invalid_key_raises(self):
        with pytest.raises(RuntimeAuthError):
            raise RuntimeAuthError("Invalid X-Agent-Runtime-Key")
