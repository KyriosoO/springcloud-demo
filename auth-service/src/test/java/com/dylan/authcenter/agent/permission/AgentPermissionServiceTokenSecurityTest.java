package com.dylan.authcenter.agent.permission;

import static org.assertj.core.api.Assertions.assertThat;

import com.dylan.authcenter.agent.permission.api.AgentPermissionErrorResponse;
import com.dylan.authcenter.agent.permission.api.AgentPermissionResolveRequest;
import com.dylan.authcenter.agent.permission.api.AgentPermissionResolveResponse;
import com.dylan.authcenter.agent.permission.api.SubjectRefDto;
import com.dylan.authcenter.service.UserService;
import com.dylan.common.security.SecurityTokenUtils;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.oauth2.jwt.Jwt;

@DisplayName("AgentPermission service token security gate")
class AgentPermissionServiceTokenSecurityTest {

    private static final Instant NOW = Instant.parse("2026-07-02T10:00:00Z");

    private AgentPermissionInternalController controller;

    @BeforeEach
    void setUp() {
        AgentPermissionProjectionService service = new AgentPermissionProjectionService(
                new UserService(),
                Clock.fixed(NOW, ZoneOffset.UTC));
        controller = new AgentPermissionInternalController(service);
    }

    @Test
    void acceptsOnlyAgentServiceTokenWithResolveScope() {
        ResponseEntity<?> entity = controller.resolve(
                serviceToken("agent-service", "other.scope agent.permission.resolve"),
                request());

        assertThat(entity.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(entity.getBody()).isInstanceOfSatisfying(AgentPermissionResolveResponse.class, body ->
                assertThat(body.subject()).isEqualTo(new SubjectRefDto("USER", "dylan")));
    }

    @Test
    void rejectsMissingToken() {
        ResponseEntity<?> entity = controller.resolve(null, request());

        assertForbiddenSecurityFailure(entity);
    }

    @Test
    void rejectsUserTokenEvenWhenItCarriesResolveScope() {
        ResponseEntity<?> entity = controller.resolve(userToken("dylan", "agent.permission.resolve"), request());

        assertForbiddenSecurityFailure(entity);
    }

    @Test
    void rejectsWrongServiceSubject() {
        ResponseEntity<?> entity = controller.resolve(
                serviceToken("other-service", "agent.permission.resolve"),
                request());

        assertForbiddenSecurityFailure(entity);
    }

    @Test
    void rejectsAgentServiceTokenWithoutResolveScope() {
        ResponseEntity<?> entity = controller.resolve(serviceToken("agent-service", "other.scope"), request());

        assertForbiddenSecurityFailure(entity);
    }

    private static void assertForbiddenSecurityFailure(ResponseEntity<?> entity) {
        assertThat(entity.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(entity.getBody()).isInstanceOfSatisfying(AgentPermissionErrorResponse.class, body -> {
            assertThat(body.requestId()).isEqualTo("req-1");
            assertThat(body.code()).isEqualTo("AGENT_PERMISSION_UNAVAILABLE");
            assertThat(body.diagnosticId()).startsWith("aperm-");
        });
    }

    private static AgentPermissionResolveRequest request() {
        return new AgentPermissionResolveRequest(
                "req-1",
                new SubjectRefDto("USER", "dylan"),
                NOW,
                NOW.plusSeconds(30));
    }

    private static Jwt serviceToken(String subject, String scope) {
        return Jwt.withTokenValue("service-token")
                .headers(headers -> headers.put("alg", "none"))
                .subject(subject)
                .issuedAt(NOW)
                .expiresAt(NOW.plusSeconds(300))
                .claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, SecurityTokenUtils.SERVICE_TOKEN_TYPE)
                .claim("scope", scope)
                .build();
    }

    private static Jwt userToken(String subject, String scope) {
        return Jwt.withTokenValue("user-token")
                .headers(headers -> headers.putAll(Map.of("alg", "none")))
                .subject(subject)
                .issuedAt(NOW)
                .expiresAt(NOW.plusSeconds(300))
                .claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, SecurityTokenUtils.USER_TOKEN_TYPE)
                .claim("scope", scope)
                .build();
    }
}
