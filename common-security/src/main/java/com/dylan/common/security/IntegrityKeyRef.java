package com.dylan.common.security;

/** 完整性签名 key 的安全引用，不包含 key material 或存储路径。 */
public record IntegrityKeyRef(String keyId, String keyVersion) {
    public IntegrityKeyRef {
        keyId = requireSafe(keyId, "keyId");
        keyVersion = requireSafe(keyVersion, "keyVersion");
    }

    private static String requireSafe(String value, String name) {
        if (value == null || !value.matches("[A-Za-z0-9._-]{1,64}")) {
            throw new IllegalArgumentException(name + " must be a safe identifier");
        }
        return value;
    }
}
