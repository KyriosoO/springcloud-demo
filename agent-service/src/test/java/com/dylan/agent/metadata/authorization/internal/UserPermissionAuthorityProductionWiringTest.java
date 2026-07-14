package com.dylan.agent.metadata.authorization.internal;

import static org.assertj.core.api.Assertions.assertThat;

import com.dylan.agent.metadata.authorization.port.UserPermissionAuthorityPort;
import com.dylan.common.security.ServiceTokenProvider;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.web.client.RestClient;

class UserPermissionAuthorityProductionWiringTest {

    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withUserConfiguration(
                    AuthServiceUserPermissionAuthorityConfiguration.class,
                    AuthorizationSecurityConfiguration.class)
            .withBean(RestClient.Builder.class, RestClient::builder)
            .withBean(ObjectMapper.class, () -> JsonMapper.builder().findAndAddModules().build())
            .withBean(Clock.class, () -> Clock.fixed(
                    Instant.parse("2026-07-02T10:00:00Z"),
                    ZoneOffset.UTC))
            .withBean(ServiceTokenProvider.class, () -> {
                ServiceTokenProvider provider = Mockito.mock(ServiceTokenProvider.class);
                Mockito.when(provider.token()).thenReturn("service-token");
                return provider;
            })
            .withPropertyValues(
                    "agent.auth-service.base-url=http://auth-service",
                    "agent.auth-service.resolve-path=/internal/agent/permissions/resolve",
                    "agent.auth-service.connect-timeout=500ms",
                    "agent.auth-service.read-timeout=2s");

    @Test
    void productionContextHasExactlyOneAuthorityPortBean() {
        contextRunner.run(context -> {
            assertThat(context).hasSingleBean(UserPermissionAuthorityPort.class);
            assertThat(context.getBean(UserPermissionAuthorityPort.class))
                    .isInstanceOf(AuthServiceUserPermissionAuthorityAdapter.class);
            assertThat(context).hasSingleBean(UserPermissionBoundary.class);
        });
    }

    @Test
    void missingServiceTokenProviderFailsStartup() {
        new ApplicationContextRunner()
                .withUserConfiguration(
                        AuthServiceUserPermissionAuthorityConfiguration.class,
                        AuthorizationSecurityConfiguration.class)
                .withBean(RestClient.Builder.class, RestClient::builder)
                .withBean(ObjectMapper.class, () -> JsonMapper.builder().findAndAddModules().build())
                .withBean(Clock.class, () -> Clock.fixed(
                        Instant.parse("2026-07-02T10:00:00Z"),
                        ZoneOffset.UTC))
                .withPropertyValues(
                        "agent.auth-service.base-url=http://auth-service",
                        "agent.auth-service.resolve-path=/internal/agent/permissions/resolve",
                        "agent.auth-service.connect-timeout=500ms",
                        "agent.auth-service.read-timeout=2s")
                .run(context -> assertThat(context).hasFailed());
    }
}
