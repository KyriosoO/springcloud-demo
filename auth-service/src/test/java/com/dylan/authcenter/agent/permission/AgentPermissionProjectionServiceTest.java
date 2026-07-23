package com.dylan.authcenter.agent.permission;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.dylan.authcenter.agent.permission.api.AgentPermissionResolveRequest;
import com.dylan.authcenter.agent.permission.api.AgentPermissionResolveResponse;
import com.dylan.authcenter.agent.permission.api.SubjectRefDto;
import com.dylan.authcenter.config.AuthRbacProperties;
import com.dylan.authcenter.service.UserService;
import com.dylan.authcenter.testsupport.AuthRbacTestFixtures;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

@DisplayName("AgentPermissionProjectionService")
class AgentPermissionProjectionServiceTest {

    private static final Instant NOW = Instant.parse("2026-07-02T10:00:00Z");

    private AgentPermissionProjectionService service;
    private AuthRbacProperties rbacProperties;

    @BeforeEach
    void setUp() {
        rbacProperties = AuthRbacTestFixtures.load();
        service = new AgentPermissionProjectionService(
                new UserService(rbacProperties),
                rbacProperties,
                Clock.fixed(NOW, ZoneOffset.UTC));
    }

    @Test
    void resolvesAdminToCompleteAgentPermissionProjection() {
        AgentPermissionResolveResponse response = service.resolve(request("dylan"));

        assertThat(response.subject()).isEqualTo(new SubjectRefDto("USER", "dylan"));
        assertThat(response.tenantRef()).isEqualTo("tenant-main");
        assertThat(response.permissionCodes()).containsExactly("agent-admin");
        assertThat(response.evidenceId()).startsWith("perm-user-");
        assertThat(response.version()).isEqualTo(rbacProperties.getRuleVersion());
        assertThat(response.allowedCapabilityIds())
                .containsExactlyInAnyOrder("query.search", "query.preview", "aggregate.compute",
                        "document.search", "document.answer", "document.summarize");
        assertThat(response.allowedDomains()).containsExactlyInAnyOrder(
                "employee", "transaction", "company_policy", "tax_policy", "knowledge_base", "literature");
        assertThat(response.filterableFields().get("employee"))
                .containsExactlyInAnyOrder("chineseName", "memberNo", "position", "workBaseSi",
                        "contactAddress", "idCardNo", "phoneNo", "email");
        assertThat(response.filterableFields().get("tax_policy"))
                .containsExactlyInAnyOrder("title", "sourceType", "effectiveDate", "tags",
                        "section", "page", "sourceUri", "snippet");
        assertThat(response.displayableFields()).isEqualTo(response.filterableFields());
        assertThat(response.allowedOperators().get("employee.chineseName"))
                .containsExactlyInAnyOrder("EQ", "CONTAINS", "CONTAINS_ANY",
                        "STARTS_WITH", "STARTS_WITH_ANY", "IN");
        assertThat(response.allowedOperators().get("transaction.amount"))
                .containsExactlyInAnyOrder("EQ", "GT", "LT");
        assertThat(response.allowedOperators().get("tax_policy.title"))
                .containsExactlyInAnyOrder("EQ", "CONTAINS", "CONTAINS_ANY");
        assertThat(response.allowedOperators().get("tax_policy.tags"))
                .containsExactlyInAnyOrder("EQ", "IN", "CONTAINS_ANY");
        assertThat(response.allowedFunctions().get("transaction.amount"))
                .containsExactlyInAnyOrder("sum", "avg", "min", "max");
        assertThat(response.readableContextTypes()).containsExactlyInAnyOrder("QUERY", "AGGREGATE", "DOCUMENT");
        assertThat(response.writableContextTypes()).containsExactlyInAnyOrder("QUERY", "AGGREGATE", "DOCUMENT");
        assertThat(response.attributes())
                .containsEntry("source", "auth-service-agent-permission")
                .containsEntry("policyTier", "admin");
        assertThat(response.resolvedAt()).isEqualTo(NOW);
        assertThat(response.validUntil()).isEqualTo(NOW.plusSeconds(30));
    }

    @Test
    void resolvesViewerToQueryOnlyProjection() {
        AgentPermissionResolveResponse response = service.resolve(request("viewer_t"));

        assertThat(response.allowedCapabilityIds()).containsExactlyInAnyOrder("query.search", "query.preview");
        assertThat(response.permissionCodes()).containsExactly("agent-viewer");
        assertThat(response.allowedDomains()).containsExactly("employee");
        assertThat(response.filterableFields().get("employee"))
                .containsExactlyInAnyOrder("chineseName", "memberNo", "position");
        assertThat(response.allowedFunctions()).isEmpty();
        assertThat(response.attributes()).containsEntry("policyTier", "viewer");
    }

    @Test
    void adminProjectionIncludesQueryPreview() {
        AgentPermissionResolveResponse response = service.resolve(request("dylan"));

        assertThat(response.allowedCapabilityIds()).contains("query.preview");
    }

    @Test
    void rejectsUnknownSubject() {
        assertThatThrownBy(() -> service.resolve(request("missing-user")))
                .isInstanceOfSatisfying(AgentPermissionException.class, ex ->
                        assertThat(ex.code()).isEqualTo(AgentPermissionErrorCode.AGENT_PERMISSION_SUBJECT_NOT_FOUND));
    }

    @Test
    void rejectsExpiredDeadline() {
        AgentPermissionResolveRequest expired = new AgentPermissionResolveRequest(
                "req-1",
                new SubjectRefDto("USER", "dylan"),
                NOW.minusSeconds(10),
                NOW.minusSeconds(1));

        assertThatThrownBy(() -> service.resolve(expired))
                .isInstanceOfSatisfying(AgentPermissionException.class, ex ->
                        assertThat(ex.code()).isEqualTo(AgentPermissionErrorCode.AGENT_PERMISSION_DEADLINE_EXCEEDED));
    }

    @Test
    void rejectsInvalidSubjectType() {
        AgentPermissionResolveRequest invalid = new AgentPermissionResolveRequest(
                "req-1",
                new SubjectRefDto("SERVICE", "dylan"),
                NOW,
                NOW.plusSeconds(30));

        assertThatThrownBy(() -> service.resolve(invalid))
                .isInstanceOfSatisfying(AgentPermissionException.class, ex ->
                        assertThat(ex.code()).isEqualTo(AgentPermissionErrorCode.AGENT_PERMISSION_INVALID_REQUEST));
    }

    @Test
    void clampsPermissionValidityToRequestDeadline() {
        AgentPermissionResolveRequest shortDeadline = new AgentPermissionResolveRequest(
                "req-1", new SubjectRefDto("USER", "dylan"), NOW, NOW.plusSeconds(5));

        AgentPermissionResolveResponse response = service.resolve(shortDeadline);

        assertThat(response.validUntil()).isEqualTo(NOW.plusSeconds(5));
    }

    private static AgentPermissionResolveRequest request(String userId) {
        return new AgentPermissionResolveRequest(
                "req-1",
                new SubjectRefDto("USER", userId),
                NOW,
                NOW.plusSeconds(30));
    }
}
