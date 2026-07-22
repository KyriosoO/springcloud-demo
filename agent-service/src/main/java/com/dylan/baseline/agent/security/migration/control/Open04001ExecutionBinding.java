package com.dylan.baseline.agent.security.migration.control;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/** 从实际执行参数重算DR-04-045环境绑定，禁止调用方直接声明摘要。 */
final class Open04001ExecutionBinding {

    private static final String CONFIG_SCHEMA = "open-04-001-security-config-v0.1";
    private static final String DATABASE_SCHEMA = "open-04-001-database-ref-v0.1";

    private Open04001ExecutionBinding() {
    }

    static String configurationDigest(
            String keyId, String keyVersion, String approverRefDigest, byte[] publicKeyDer) {
        return digest(CONFIG_SCHEMA, keyId, keyVersion, approverRefDigest, sha256(publicKeyDer));
    }

    static String databaseRefDigest(String jdbcUrl, String databaseUser) {
        return digest(DATABASE_SCHEMA, jdbcUrl, databaseUser);
    }

    private static String digest(String schema, String... values) {
        StringBuilder canonical = new StringBuilder(schema);
        for (String value : values) {
            if (value == null || value.isBlank() || value.indexOf('\0') >= 0) {
                throw new IllegalArgumentException("execution binding values must be non-blank and contain no NUL");
            }
            canonical.append('\0').append(value);
        }
        return sha256(canonical.toString().getBytes(StandardCharsets.UTF_8));
    }

    private static String sha256(byte[] value) {
        try {
            return java.util.HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }
}
