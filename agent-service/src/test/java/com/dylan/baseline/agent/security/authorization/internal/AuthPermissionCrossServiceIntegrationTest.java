package com.dylan.baseline.agent.security.authorization.internal;

import static org.assertj.core.api.Assertions.assertThat;

import com.dylan.authcenter.AuthServiceApplication;
import com.dylan.baseline.agent.security.authorization.ResolvedAuthPermission;
import com.dylan.baseline.agent.security.authorization.SubjectRef;
import com.dylan.common.security.JwtKeyProvider;
import com.dylan.common.security.ServiceTokenProperties;
import com.dylan.common.security.ServiceTokenProvider;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.http.HttpClient;
import java.time.Clock;
import java.time.Instant;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.servlet.context.ServletWebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.web.client.RestClient;

/** 使用真实Auth安全过滤链、服务JWT和HTTP接口验证运行接线。 */
class AuthPermissionCrossServiceIntegrationTest {

    private static ConfigurableApplicationContext authContext;
    private static HttpAuthPermissionAuthorityAdapter adapter;

    @BeforeAll
    static void startAuthService() {
        authContext = new SpringApplicationBuilder(AuthServiceApplication.class)
                .web(WebApplicationType.SERVLET)
                .properties(Map.ofEntries(
                        Map.entry("server.port", "0"),
                        Map.entry("spring.application.name", "auth-service"),
                        Map.entry("spring.config.import", "classpath:agent-rbac.yml"),
                        Map.entry("spring.cloud.config.enabled", "false"),
                        Map.entry("eureka.client.enabled", "false"),
                        Map.entry("eureka.client.register-with-eureka", "false"),
                        Map.entry("eureka.client.fetch-registry", "false"),
                        Map.entry("common.security.secrets.allow-config-values", "true"),
                        Map.entry("common.security.secrets.source-order[0]", "config"),
                        Map.entry("common.security.secrets.jwt.active-key-id", "ACTIVE"),
                        Map.entry("common.security.secrets.jwt.keys.ACTIVE.value",
                                "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")))
                .run();
        int port = ((ServletWebServerApplicationContext) authContext).getWebServer().getPort();
        AuthPermissionClientProperties properties = new AuthPermissionClientProperties();
        properties.setBaseUrl("http://127.0.0.1:" + port);
        properties.afterPropertiesSet();
        ServiceTokenProperties tokenProperties = new ServiceTokenProperties();
        tokenProperties.setServiceId("agent-service");
        tokenProperties.setScopes(java.util.List.of("agent.permission.resolve"));
        ServiceTokenProvider tokenProvider = new ServiceTokenProvider(
                authContext.getBean(JwtEncoder.class),
                tokenProperties,
                authContext.getEnvironment(),
                authContext.getBean(JwtKeyProvider.class));
        HttpClient httpClient = HttpClient.newHttpClient();
        AuthPermissionRestClientFactory factory = readTimeout -> {
            JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
            requestFactory.setReadTimeout(readTimeout);
            return RestClient.builder()
                    .baseUrl(properties.getBaseUrl())
                    .requestFactory(requestFactory)
                    .build();
        };
        Clock clock = Clock.systemUTC();
        adapter = new HttpAuthPermissionAuthorityAdapter(
                factory,
                properties,
                tokenProvider,
                authContext.getBean(ObjectMapper.class),
                new AuthPermissionAuthorityAdapter(clock),
                clock);
    }

    @AfterAll
    static void stopAuthService() {
        if (authContext != null) {
            authContext.close();
        }
    }

    @Test
    void resolvesAllKnownSubjectsAcrossTheRealServiceBoundary() {
        Map<String, String> expectedCodes = Map.of(
                "admin", "agent-admin",
                "dylan", "agent-admin",
                "viewer_t", "agent-viewer");

        expectedCodes.forEach((subjectId, permissionCode) -> {
            Instant deadline = Instant.now().plusSeconds(10);
            ResolvedAuthPermission resolved = adapter.resolveCurrent(
                    new SubjectRef("USER", subjectId), "tenant-main", deadline);
            assertThat(resolved.authorizationFacts().tenantRef()).isEqualTo("tenant-main");
            assertThat(resolved.authorizationFacts().permissionCodes()).containsExactly(permissionCode);
            assertThat(resolved.authorizationFacts().validUntil()).isBeforeOrEqualTo(deadline);
            assertThat(resolved.legacyFieldView().filterableFields()).isNotEmpty();
        });
    }
}
