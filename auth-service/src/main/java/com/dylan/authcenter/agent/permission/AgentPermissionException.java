package com.dylan.authcenter.agent.permission;

/**
 * 权限投影内部异常，只携带 typed code，避免异常链路暴露权限正文。
 */
public final class AgentPermissionException extends RuntimeException {

    private final AgentPermissionErrorCode code;

    public AgentPermissionException(AgentPermissionErrorCode code) {
        super(code.message());
        this.code = code;
    }

    public AgentPermissionErrorCode code() {
        return code;
    }
}
