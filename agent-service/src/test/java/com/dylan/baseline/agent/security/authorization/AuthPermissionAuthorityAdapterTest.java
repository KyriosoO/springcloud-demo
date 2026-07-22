package com.dylan.baseline.agent.security.authorization;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.dylan.baseline.agent.security.authorization.internal.AuthPermissionAuthorityAdapter;
import com.dylan.baseline.agent.security.authorization.internal.AuthPermissionValidationException;
import com.dylan.baseline.agent.security.authorization.internal.AuthPermissionWireResponse;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;

class AuthPermissionAuthorityAdapterTest {

    private static final Instant NOW = Instant.parse("2026-07-22T01:00:00Z");
    private static final SubjectRef SUBJECT = new SubjectRef("USER", "dylan");
    private final AuthPermissionAuthorityAdapter adapter =
            new AuthPermissionAuthorityAdapter(Clock.fixed(NOW, ZoneOffset.UTC));

    @Test
    void separatesAuthFactsFromLegacyFieldView() {
        ResolvedAuthPermission resolved = adapter.map(response(), SUBJECT, "tenant-main", NOW.plusSeconds(30));

        assertThat(resolved.authorizationFacts().permissionCodes()).containsExactly("agent-admin");
        assertThat(resolved.authorizationFacts().tenantRef()).isEqualTo("tenant-main");
        assertThat(resolved.legacyFieldView().filterableFields())
                .containsEntry("employee", Set.of("chineseName", "memberNo"));
    }

    @Test
    void rejectsSubjectTenantAndValidityMismatch() {
        assertThatThrownBy(() -> adapter.map(response(), new SubjectRef("USER", "other"),
                "tenant-main", NOW.plusSeconds(30)))
                .isInstanceOfSatisfying(AuthPermissionValidationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_SUBJECT_MISMATCH"));
        assertThatThrownBy(() -> adapter.map(response(), SUBJECT, "tenant-other", NOW.plusSeconds(30)))
                .isInstanceOfSatisfying(AuthPermissionValidationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_TENANT_UNVERIFIED"));
        assertThatThrownBy(() -> adapter.map(response(), SUBJECT, "tenant-main", NOW))
                .isInstanceOfSatisfying(AuthPermissionValidationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_AUTH_FACT_STALE"));
        assertThatThrownBy(() -> adapter.map(response(), SUBJECT, "tenant-main", NOW.plusSeconds(10)))
                .isInstanceOfSatisfying(AuthPermissionValidationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_AUTH_FACT_STALE"));
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
                Map.of("employee", Set.of("chineseName", "memberNo")),
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
