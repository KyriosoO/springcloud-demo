package com.dylan.agent.metadata.authorization.internal;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withResourceNotFound;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.metadata.authorization.port.UserPermissionAuthorityException;
import com.dylan.agent.metadata.authorization.port.UserPermissionAuthorityFailure;
import com.dylan.common.security.ServiceTokenProvider;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

@DisplayName("AuthServiceUserPermissionAuthorityAdapter")
class AuthServiceUserPermissionAuthorityAdapterTest {

    private static final Instant NOW = Instant.parse("2026-07-02T10:00:00Z");
    private static final ExecutionSubjectRef SUBJECT = new ExecutionSubjectRef("user", "dylan");

    private ObjectMapper objectMapper;
    private MockRestServiceServer server;
    private AuthServiceUserPermissionAuthorityAdapter adapter;

    @BeforeEach
    void setUp() {
        objectMapper = JsonMapper.builder().findAndAddModules().build();
        RestClient.Builder builder = RestClient.builder()
                .messageConverters(converters ->
                        converters.add(0, new MappingJackson2HttpMessageConverter(objectMapper)))
                .baseUrl("http://auth-service");
        server = MockRestServiceServer.bindTo(builder).build();
        adapter = new AuthServiceUserPermissionAuthorityAdapter(
                builder.build(),
                properties(),
                objectMapper,
                tokenProvider("service-token"),
                Clock.fixed(NOW, ZoneOffset.UTC));
    }

    @Test
    void resolvesProjectionFromAuthService() throws Exception {
        server.expect(requestTo("http://auth-service/internal/agent/permissions/resolve"))
                .andExpect(header(HttpHeaders.AUTHORIZATION, "Bearer service-token"))
                .andExpect(jsonPath("$.subject.type").value("USER"))
                .andExpect(jsonPath("$.subject.id").value("dylan"))
                .andExpect(jsonPath("$.agentId").value("agent-default"))
                .andRespond(withSuccess(successBody("dylan"), MediaType.APPLICATION_JSON));

        var permission = adapter.resolveCurrent(SUBJECT, NOW.plusSeconds(30));

        assertThat(permission.subject()).isEqualTo(SUBJECT);
        assertThat(permission.evidenceId()).isEqualTo("perm-1");
        assertThat(permission.version()).isEqualTo("authz-v1");
        assertThat(permission.allowedCapabilityIds()).containsExactly("query.search");
        assertThat(permission.allowedDomains()).containsExactly("employee");
        assertThat(permission.allowedOperators().get("employee.chineseName"))
                .containsExactly(AgentOperator.EQ);
        assertThat(permission.attributes()).containsEntry("source", "auth-service-agent-permission");
        server.verify();
    }

    @Test
    void rejectsSubjectMismatch() {
        server.expect(requestTo("http://auth-service/internal/agent/permissions/resolve"))
                .andRespond(withSuccess(successBody("other-user"), MediaType.APPLICATION_JSON));

        assertFailure(UserPermissionAuthorityFailure.INVALID_RESPONSE,
                () -> adapter.resolveCurrent(SUBJECT, NOW.plusSeconds(30)));
    }

    @Test
    void rejectsInvalidOperator() {
        server.expect(requestTo("http://auth-service/internal/agent/permissions/resolve"))
                .andRespond(withSuccess(successBody("dylan").replace("\"EQ\"", "\"UNKNOWN\""),
                        MediaType.APPLICATION_JSON));

        assertFailure(UserPermissionAuthorityFailure.INVALID_RESPONSE,
                () -> adapter.resolveCurrent(SUBJECT, NOW.plusSeconds(30)));
    }

    @Test
    void mapsMalformedProjectionToInvalidResponse() {
        server.expect(requestTo("http://auth-service/internal/agent/permissions/resolve"))
                .andRespond(withSuccess(malformedProjectionBody(), MediaType.APPLICATION_JSON));

        assertFailure(UserPermissionAuthorityFailure.INVALID_RESPONSE,
                () -> adapter.resolveCurrent(SUBJECT, NOW.plusSeconds(30)),
                "auth-permission-invalid-projection");
    }

    @Test
    void mapsSubjectNotFound() {
        server.expect(requestTo("http://auth-service/internal/agent/permissions/resolve"))
                .andRespond(withResourceNotFound()
                        .contentType(MediaType.APPLICATION_JSON)
                        .body(errorBody("AGENT_PERMISSION_SUBJECT_NOT_FOUND", "diag-404")));

        assertFailure(UserPermissionAuthorityFailure.SUBJECT_NOT_FOUND,
                () -> adapter.resolveCurrent(SUBJECT, NOW.plusSeconds(30)),
                "diag-404");
    }

    @Test
    void mapsForbiddenToUnavailable() {
        server.expect(requestTo("http://auth-service/internal/agent/permissions/resolve"))
                .andRespond(withStatus(HttpStatus.FORBIDDEN)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body(errorBody("AGENT_PERMISSION_UNAVAILABLE", "diag-403")));

        assertFailure(UserPermissionAuthorityFailure.UNAVAILABLE,
                () -> adapter.resolveCurrent(SUBJECT, NOW.plusSeconds(30)),
                "diag-403");
    }

    @Test
    void mapsGatewayTimeoutToDeadlineExceeded() {
        server.expect(requestTo("http://auth-service/internal/agent/permissions/resolve"))
                .andRespond(withStatus(HttpStatus.GATEWAY_TIMEOUT)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body(errorBody("AGENT_PERMISSION_DEADLINE_EXCEEDED", "diag-504")));

        assertFailure(UserPermissionAuthorityFailure.DEADLINE_EXCEEDED,
                () -> adapter.resolveCurrent(SUBJECT, NOW.plusSeconds(30)),
                "diag-504");
    }

    @Test
    void rejectsExpiredDeadlineBeforeCallingAuthService() {
        assertFailure(UserPermissionAuthorityFailure.DEADLINE_EXCEEDED,
                () -> adapter.resolveCurrent(SUBJECT, NOW.minusSeconds(1)));
        server.verify();
    }

    private static AgentProperties.AuthServiceProperties properties() {
        AgentProperties.AuthServiceProperties properties = new AgentProperties.AuthServiceProperties();
        properties.setBaseUrl("http://auth-service");
        properties.setResolvePath("/internal/agent/permissions/resolve");
        properties.setAgentId("agent-default");
        properties.setProfileId("profile-v1");
        properties.setScopeType("CONVERSATION");
        properties.setScopeId("agent-permission-authority");
        return properties;
    }

    private static ServiceTokenProvider tokenProvider(String token) {
        ServiceTokenProvider provider = Mockito.mock(ServiceTokenProvider.class);
        Mockito.when(provider.token()).thenReturn(token);
        return provider;
    }

    private String successBody(String subjectId) {
        try {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("subject", Map.of("type", "USER", "id", subjectId));
            body.put("evidenceId", "perm-1");
            body.put("version", "authz-v1");
            body.put("allowedCapabilityIds", Set.of("query.search"));
            body.put("allowedDomains", Set.of("employee"));
            body.put("filterableFields", Map.of("employee", Set.of("chineseName")));
            body.put("displayableFields", Map.of("employee", Set.of("chineseName")));
            body.put("allowedOperators", Map.of("employee.chineseName", Set.of("EQ")));
            body.put("allowedFunctions", Map.of());
            body.put("readableContextTypes", Set.of("QUERY"));
            body.put("writableContextTypes", Set.of("QUERY"));
            body.put("attributes", Map.of("source", "auth-service-agent-permission"));
            body.put("resolvedAt", NOW);
            return objectMapper.writeValueAsString(body);
        } catch (Exception ex) {
            throw new IllegalStateException(ex);
        }
    }

    private static String errorBody(String code, String diagnosticId) {
        return """
                {
                  "requestId": "req-1",
                  "code": "%s",
                  "message": "safe error",
                  "diagnosticId": "%s"
                }
                """.formatted(code, diagnosticId);
    }

    private static String malformedProjectionBody() {
        return """
                {
                  "subject": {"type": "USER", "id": "dylan"},
                  "evidenceId": "perm-1",
                  "version": "authz-v1",
                  "allowedCapabilityIds": ["query.search", null],
                  "allowedDomains": ["employee"],
                  "filterableFields": {"employee": ["chineseName"]},
                  "displayableFields": {"employee": ["chineseName"]},
                  "allowedOperators": {"employee.chineseName": ["EQ"]},
                  "allowedFunctions": {},
                  "readableContextTypes": ["QUERY"],
                  "writableContextTypes": ["QUERY"],
                  "attributes": {"source": "auth-service-agent-permission"},
                  "resolvedAt": "2026-07-02T10:00:00Z"
                }
                """;
    }

    private static void assertFailure(
            UserPermissionAuthorityFailure expected,
            ThrowingCall call) {
        assertFailure(expected, call, null);
    }

    private static void assertFailure(
            UserPermissionAuthorityFailure expected,
            ThrowingCall call,
            String diagnosticId) {
        assertThatThrownBy(call::run)
                .isInstanceOfSatisfying(UserPermissionAuthorityException.class, ex -> {
                    assertThat(ex.failure()).isEqualTo(expected);
                    if (diagnosticId != null) {
                        assertThat(ex.diagnosticId()).isEqualTo(diagnosticId);
                    }
                });
    }

    @FunctionalInterface
    private interface ThrowingCall {
        void run() throws Exception;
    }
}
