package com.dylan.baseline.agent.security.authorization.internal;

public final class AuthPermissionValidationException extends RuntimeException {

    private final String code;

    public AuthPermissionValidationException(String code) {
        super(code);
        this.code = code;
    }

    public AuthPermissionValidationException(String code, Throwable cause) {
        super(code, cause);
        this.code = code;
    }

    public String code() {
        return code;
    }
}
