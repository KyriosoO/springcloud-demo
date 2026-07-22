package com.dylan.baseline.agent.security.migration;

/** Auth字段迁移阶段的稳定失败码，不包含字段或规则正文。 */
public final class AuthFieldMigrationException extends RuntimeException {

    private final String code;

    public AuthFieldMigrationException(String code, String message) {
        super(message);
        this.code = code;
    }

    public String code() {
        return code;
    }
}
