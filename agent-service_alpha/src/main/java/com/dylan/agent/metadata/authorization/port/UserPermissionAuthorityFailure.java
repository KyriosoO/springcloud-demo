package com.dylan.agent.metadata.authorization.port;

/**
 * 外部用户权限权威源的 typed failure。
 */
public enum UserPermissionAuthorityFailure {
    UNAVAILABLE,
    DEADLINE_EXCEEDED,
    SUBJECT_NOT_FOUND,
    INVALID_RESPONSE
}
