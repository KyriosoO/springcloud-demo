package com.dylan.agent.metadata.authorization.port;

import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.metadata.authorization.model.UserPermission;

import java.time.Instant;

/**
 * D02 允许消费的唯一外部用户权限 SPI。
 */
public interface UserPermissionAuthorityPort {

    UserPermission resolveCurrent(
            ExecutionSubjectRef subject,
            Instant absoluteDeadline) throws UserPermissionAuthorityException;
}
