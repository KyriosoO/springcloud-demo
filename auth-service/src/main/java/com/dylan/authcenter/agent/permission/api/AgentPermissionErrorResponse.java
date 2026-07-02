package com.dylan.authcenter.agent.permission.api;

/**
 * 内部权限接口的安全错误响应，message/diagnosticId 不携带 JWT 或权限正文。
 */
public record AgentPermissionErrorResponse(
        String requestId,
        String code,
        String message,
        String diagnosticId) {
}
