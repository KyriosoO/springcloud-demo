package com.dylan.agent.metadata.authorization.port;

import java.util.Objects;

/**
 * 权限权威源异常。message/diagnosticId 不得包含权限正文、JWT 或外部响应体。
 */
public final class UserPermissionAuthorityException extends Exception {

    private final UserPermissionAuthorityFailure failure;
    private final String diagnosticId;

    public UserPermissionAuthorityException(
            UserPermissionAuthorityFailure failure,
            String diagnosticId,
            Throwable cause) {
        super("User permission authority failed: " + Objects.requireNonNull(failure), cause);
        this.failure = failure;
        this.diagnosticId = requireNonBlank(diagnosticId);
    }

    public UserPermissionAuthorityFailure failure() {
        return failure;
    }

    public String diagnosticId() {
        return diagnosticId;
    }

    private static String requireNonBlank(String value) {
        Objects.requireNonNull(value, "diagnosticId must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException("diagnosticId must not be blank");
        }
        return normalized;
    }
}
