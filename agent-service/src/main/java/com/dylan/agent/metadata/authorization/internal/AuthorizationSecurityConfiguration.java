package com.dylan.agent.metadata.authorization.internal;

import com.dylan.agent.metadata.authorization.port.UserPermissionAuthorityPort;

import java.time.Clock;
import java.util.List;
import java.util.Objects;

/**
 * 用户权限边界装配门禁。
 *
 * <p>该类先作为可测试工厂存在；生产 Adapter 接入时由 D03/D04 组合根激活为
 * Spring bean，仍必须复用这里的“恰好一个 SPI”规则。</p>
 */
public final class AuthorizationSecurityConfiguration {

    public UserPermissionBoundary userPermissionBoundary(
            List<UserPermissionAuthorityPort> ports,
            Clock clock) {
        Objects.requireNonNull(ports, "ports must not be null");
        if (ports.size() != 1) {
            throw new IllegalStateException(
                    "Exactly one UserPermissionAuthorityPort is required, got " + ports.size());
        }
        return new UserPermissionBoundary(ports.get(0), clock);
    }
}
