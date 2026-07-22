package com.dylan.baseline.agent.security.authorization.internal;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.dylan.baseline.agent.security.authorization.ResolvedAuthPermission;
import com.dylan.baseline.agent.security.authorization.SubjectRef;
import com.dylan.common.security.ServiceTokenProvider;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.net.http.HttpClient;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

class HttpAuthPermissionAuthorityAdapterTest {

    private static final Instant NOW = Instant.parse("2026-07-22T02:00:00Z");
    private static final SubjectRef SUBJECT = new SubjectRef("USER", "dylan");
    private HttpServer server;

    @AfterEach
    void stopServer() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    void callsAuthOnceWithServiceTokenAndMapsStrictResponse() throws Exception {
        AtomicInteger calls = new AtomicInteger();
        ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/internal/agent/permissions/resolve", exchange -> {
            calls.incrementAndGet();
            assertThat(exchange.getRequestHeaders().getFirst("Authorization"))
                    .isEqualTo("Bearer signed-service-token");
            exchange.getRequestBody().readAllBytes();
            byte[] body = objectMapper.writeValueAsBytes(response());
            exchange.getResponseHeaders().set("Content-Type", MediaType.APPLICATION_JSON_VALUE);
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();

        ResolvedAuthPermission resolved = adapter(objectMapper)
                .resolveCurrent(SUBJECT, "tenant-main", NOW.plusSeconds(30));

        assertThat(calls).hasValue(1);
        assertThat(resolved.authorizationFacts().permissionCodes()).containsExactly("agent-admin");
        assertThat(resolved.legacyFieldView().filterableFields())
                .containsEntry("employee", Set.of("chineseName"));
    }

    @Test
    void failsClosedWithoutRetryWhenAuthIsUnavailable() throws Exception {
        AtomicInteger calls = new AtomicInteger();
        ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/internal/agent/permissions/resolve", exchange -> {
            calls.incrementAndGet();
            exchange.sendResponseHeaders(503, -1);
            exchange.close();
        });
        server.start();

        assertThatThrownBy(() -> adapter(objectMapper)
                .resolveCurrent(SUBJECT, "tenant-main", NOW.plusSeconds(30)))
                .isInstanceOfSatisfying(AuthPermissionValidationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_AUTH_FACT_UNAVAILABLE"));
        assertThat(calls).hasValue(1);
    }

    @ParameterizedTest
    @ValueSource(ints = {400, 404})
    void mapsAuthRejectionToUnavailableWithoutRetry(int status) throws Exception {
        AtomicInteger calls = new AtomicInteger();
        ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/internal/agent/permissions/resolve", exchange -> {
            calls.incrementAndGet();
            exchange.sendResponseHeaders(status, -1);
            exchange.close();
        });
        server.start();

        assertThatThrownBy(() -> adapter(objectMapper)
                .resolveCurrent(SUBJECT, "tenant-main", NOW.plusSeconds(30)))
                .isInstanceOfSatisfying(AuthPermissionValidationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_AUTH_FACT_UNAVAILABLE"));
        assertThat(calls).hasValue(1);
    }

    private HttpAuthPermissionAuthorityAdapter adapter(ObjectMapper objectMapper) {
        AuthPermissionClientProperties properties = new AuthPermissionClientProperties();
        properties.setBaseUrl("http://127.0.0.1:" + server.getAddress().getPort());
        properties.afterPropertiesSet();
        ServiceTokenProvider tokenProvider = mock(ServiceTokenProvider.class);
        when(tokenProvider.token()).thenReturn("signed-service-token");
        HttpClient httpClient = HttpClient.newHttpClient();
        AuthPermissionRestClientFactory factory = readTimeout -> {
            JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
            requestFactory.setReadTimeout(readTimeout);
            return RestClient.builder()
                    .baseUrl(properties.getBaseUrl())
                    .requestFactory(requestFactory)
                    .build();
        };
        Clock clock = Clock.fixed(NOW, ZoneOffset.UTC);
        return new HttpAuthPermissionAuthorityAdapter(
                factory,
                properties,
                tokenProvider,
                objectMapper,
                new AuthPermissionAuthorityAdapter(clock),
                clock);
    }

    private static AuthPermissionWireResponse response() {
        return new AuthPermissionWireResponse(
                SUBJECT,
                "tenant-main",
                Set.of("agent-admin"),
                "perm-user-1234",
                "authz-v1",
                Set.of("query.search"),
                Set.of("employee"),
                Map.of("employee", Set.of("chineseName")),
                Map.of("employee", Set.of("chineseName")),
                Map.of("employee.chineseName", Set.of("EQ")),
                Map.of(),
                Set.of("QUERY"),
                Set.of("QUERY"),
                Map.of("source", "auth-service-agent-permission"),
                NOW.minusSeconds(1),
                NOW.plusSeconds(20));
    }
}
