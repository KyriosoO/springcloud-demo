package com.dylan.baseline.agent.security.authorization;

import java.time.Instant;

/** 获取当前 Auth RBAC 上界的唯一运行时端口。 */
public interface AuthPermissionAuthorityPort {

    ResolvedAuthPermission resolveCurrent(
            SubjectRef expectedSubject,
            String expectedTenantRef,
            Instant absoluteDeadline);
}
