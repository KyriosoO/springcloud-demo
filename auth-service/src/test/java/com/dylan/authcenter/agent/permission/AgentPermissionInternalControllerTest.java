package com.dylan.authcenter.agent.permission;

import static org.assertj.core.api.Assertions.assertThat;

import com.dylan.authcenter.agent.permission.api.AgentPermissionErrorResponse;
import com.dylan.authcenter.agent.permission.api.AgentPermissionResolveRequest;
import com.dylan.authcenter.agent.permission.api.AgentPermissionResolveResponse;
import com.dylan.authcenter.agent.permission.api.SubjectRefDto;
import com.dylan.authcenter.config.AuthRbacProperties;
import com.dylan.authcenter.service.UserService;
import com.dylan.authcenter.testsupport.AuthRbacTestFixtures;
import com.dylan.common.security.SecurityTokenUtils;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.oauth2.jwt.Jwt;

@DisplayName("AgentPermissionInternalController")
class AgentPermissionInternalControllerTest {

    private static final Instant NOW = Instant.parse("2026-07-02T10:00:00Z");

    private AgentPermissionInternalController controller;
    private AuthRbacProperties rbacProperties;

    @BeforeEach
    void setUp() {
        rbacProperties = AuthRbacTestFixtures.load();
        AgentPermissionProjectionService service = new AgentPermissionProjectionService(
                new UserService(rbacProperties),
                rbacProperties,
                Clock.fixed(NOW, ZoneOffset.UTC));
        controller = new AgentPermissionInternalController(service);
    }

    @Test
    void resolvesPermissionForAuthorizedAgentServiceToken() {
        ResponseEntity<?> entity = controller.resolve(serviceToken(
                "agent-service",
                "agent.permission.resolve other.scope"),
                request("dylan"));

        assertThat(entity.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(entity.getBody()).isInstanceOfSatisfying(AgentPermissionResolveResponse.class, body -> {
            assertThat(body.subject()).isEqualTo(new SubjectRefDto("USER", "dylan"));
            assertThat(body.allowedCapabilityIds())
                    .containsExactlyInAnyOrder("query.search", "query.preview", "aggregate.compute",
                            "document.search", "document.answer", "document.summarize");
            assertThat(body.version()).isEqualTo(rbacProperties.getRuleVersion());
        });
    }

    @Test
    void rejectsUserToken() {
        ResponseEntity<?> entity = controller.resolve(userToken("dylan"), request("dylan"));

        assertThat(entity.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(entity.getBody()).isInstanceOfSatisfying(AgentPermissionErrorResponse.class, body -> {
            assertThat(body.requestId()).isEqualTo("req-1");
            assertThat(body.code()).isEqualTo("AGENT_PERMISSION_UNAVAILABLE");
            assertThat(body.diagnosticId()).startsWith("aperm-");
        });
    }

    @Test
    void rejectsWrongServiceIdentity() {
        ResponseEntity<?> entity = controller.resolve(serviceToken(
                "other-service",
                "agent.permission.resolve"),
                request("dylan"));

        assertThat(entity.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(entity.getBody()).isInstanceOfSatisfying(AgentPermissionErrorResponse.class, body ->
                assertThat(body.code()).isEqualTo("AGENT_PERMISSION_UNAVAILABLE"));
    }

    @Test
    void rejectsServiceTokenWithoutRequiredScope() {
        ResponseEntity<?> entity = controller.resolve(serviceToken(
                "agent-service",
                "other.scope"),
                request("dylan"));

        assertThat(entity.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(entity.getBody()).isInstanceOfSatisfying(AgentPermissionErrorResponse.class, body ->
                assertThat(body.code()).isEqualTo("AGENT_PERMISSION_UNAVAILABLE"));
    }

    @Test
    void mapsUnknownSubjectToNotFoundErrorBody() {
        ResponseEntity<?> entity = controller.resolve(serviceToken(
                "agent-service",
                "agent.permission.resolve"),
                request("missing-user"));

        assertThat(entity.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(entity.getBody()).isInstanceOfSatisfying(AgentPermissionErrorResponse.class, body -> {
            assertThat(body.requestId()).isEqualTo("req-1");
            assertThat(body.code()).isEqualTo("AGENT_PERMISSION_SUBJECT_NOT_FOUND");
            assertThat(body.diagnosticId()).startsWith("aperm-");
        });
    }

    private static AgentPermissionResolveRequest request(String userId) {
        return new AgentPermissionResolveRequest(
                "req-1",
                new SubjectRefDto("USER", userId),
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

    private static Jwt userToken(String subject) {
        return Jwt.withTokenValue("user-token")
                .headers(headers -> headers.putAll(Map.of("alg", "none")))
                .subject(subject)
                .issuedAt(NOW)
                .expiresAt(NOW.plusSeconds(300))
                .claim("role", Set.of("agent:admin"))
                .build();
    }
}
