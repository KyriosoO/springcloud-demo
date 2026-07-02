package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Clock;
import java.time.ZoneOffset;
import java.util.List;

import org.junit.jupiter.api.Test;

import com.dylan.agent.metadata.authorization.internal.AuthorizationSecurityConfiguration;
import com.dylan.agent.metadata.authorization.port.UserPermissionAuthorityPort;

class UserPermissionAuthorityWiringTest {
    @Test
    void requiresExactlyOneProductionAuthorityPort() {
        AuthorizationSecurityConfiguration configuration = new AuthorizationSecurityConfiguration();
        UserPermissionAuthorityPort port = (subject, deadline) -> MetadataTestSupport.permission(subject);
        Clock clock = Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC);

        assertThatThrownBy(() -> configuration.userPermissionBoundary(List.of(), clock))
                .isInstanceOf(IllegalStateException.class);
        assertThatThrownBy(() -> configuration.userPermissionBoundary(List.of(port, port), clock))
                .isInstanceOf(IllegalStateException.class);
    }
}
