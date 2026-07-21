package com.dylan.agent.metadata.authorization.internal;

import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.KernelErrorCode;
import com.dylan.agent.metadata.authorization.model.UserPermission;
import com.dylan.agent.metadata.authorization.port.UserPermissionAuthorityException;
import com.dylan.agent.metadata.authorization.port.UserPermissionAuthorityFailure;
import com.dylan.agent.metadata.authorization.port.UserPermissionAuthorityPort;

import java.time.Clock;
import java.time.Instant;
import java.util.Objects;

/**
 * 用户权限权威源的 fail-closed 边界。
 *
 * <p>本边界只调用唯一外部 SPI，不读取 JWT、本地角色、AgentProperties
 * 或“上次允许”缓存。</p>
 */
public final class UserPermissionBoundary {

    private final UserPermissionAuthorityPort authorityPort;
    private final Clock clock;

    public UserPermissionBoundary(UserPermissionAuthorityPort authorityPort, Clock clock) {
        this.authorityPort = Objects.requireNonNull(authorityPort);
        this.clock = Objects.requireNonNull(clock);
    }

    public UserPermission resolve(ExecutionSubjectRef subject, Instant absoluteDeadline) {
        Objects.requireNonNull(subject, "subject must not be null");
        Objects.requireNonNull(absoluteDeadline, "absoluteDeadline must not be null");
        assertDeadline(absoluteDeadline);
        try {
            UserPermission permission = authorityPort.resolveCurrent(subject, absoluteDeadline);
            assertDeadline(absoluteDeadline);
            validateResponse(subject, permission);
            return permission;
        } catch (UserPermissionAuthorityException ex) {
            if (ex.failure() == UserPermissionAuthorityFailure.DEADLINE_EXCEEDED) {
                throw new UserPermissionBoundaryException(
                        KernelErrorCode.DEADLINE_EXCEEDED, ex.diagnosticId(), ex);
            }
            throw new UserPermissionBoundaryException(
                    KernelErrorCode.PERMISSION_UNAVAILABLE, ex.diagnosticId(), ex);
        }
    }

    private void validateResponse(ExecutionSubjectRef expected, UserPermission permission) {
        if (permission == null) {
            throw new UserPermissionBoundaryException(
                    KernelErrorCode.PERMISSION_UNAVAILABLE,
                    "permission-null-response",
                    null);
        }
        if (!expected.equals(permission.subject())) {
            throw new UserPermissionBoundaryException(
                    KernelErrorCode.PERMISSION_UNAVAILABLE,
                    "permission-subject-mismatch",
                    null);
        }
        if (permission.resolvedAt().isAfter(clock.instant())) {
            throw new UserPermissionBoundaryException(
                    KernelErrorCode.PERMISSION_UNAVAILABLE,
                    "permission-resolved-at-future",
                    null);
        }
    }

    private void assertDeadline(Instant absoluteDeadline) {
        if (!clock.instant().isBefore(absoluteDeadline)) {
            throw new UserPermissionBoundaryException(
                    KernelErrorCode.DEADLINE_EXCEEDED,
                    "permission-deadline-exceeded",
                    null);
        }
    }

    public static final class UserPermissionBoundaryException extends RuntimeException {
        private final KernelErrorCode errorCode;
        private final String diagnosticId;

        UserPermissionBoundaryException(
                KernelErrorCode errorCode,
                String diagnosticId,
                Throwable cause) {
            super("User permission resolution failed: " + errorCode, cause);
            this.errorCode = Objects.requireNonNull(errorCode);
            this.diagnosticId = Objects.requireNonNull(diagnosticId);
        }

        public KernelErrorCode errorCode() {
            return errorCode;
        }

        public String diagnosticId() {
            return diagnosticId;
        }
    }
}
