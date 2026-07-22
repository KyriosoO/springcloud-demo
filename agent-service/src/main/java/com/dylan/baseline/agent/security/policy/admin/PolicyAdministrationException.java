package com.dylan.baseline.agent.security.policy.admin;

/** 策略管理面稳定失败码；不得回退为放行。 */
public final class PolicyAdministrationException extends RuntimeException {

    private final String code;

    public PolicyAdministrationException(String code, String message) {
        super(message);
        this.code = code;
    }

    public PolicyAdministrationException(String code, String message, Throwable cause) {
        super(message, cause);
        this.code = code;
    }

    public String code() {
        return code;
    }
}
