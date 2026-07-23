package com.dylan.authcenter.agent.permission;

import org.springframework.http.HttpStatus;

/**
 * 内部权限接口错误码。HTTP 状态需要与 agent-service Adapter 的 failure 映射保持一致。
 */
enum AgentPermissionErrorCode {
    AGENT_PERMISSION_SUBJECT_NOT_FOUND(HttpStatus.NOT_FOUND, "Subject permission projection was not found."),
    AGENT_PERMISSION_DEADLINE_EXCEEDED(HttpStatus.GATEWAY_TIMEOUT, "Permission projection deadline was exceeded."),
    AGENT_PERMISSION_UNAVAILABLE(HttpStatus.SERVICE_UNAVAILABLE, "Permission projection is unavailable."),
    AGENT_PERMISSION_INVALID_REQUEST(HttpStatus.BAD_REQUEST, "Permission projection request is invalid."),
    AGENT_PERMISSION_INTERNAL_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "Permission projection failed.");

    private final HttpStatus status;
    private final String message;

    AgentPermissionErrorCode(HttpStatus status, String message) {
        this.status = status;
        this.message = message;
    }

    HttpStatus status() {
        return status;
    }

    String message() {
        return message;
    }
}
