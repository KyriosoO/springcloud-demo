package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.document.DocumentAclScope;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.stream.IntStream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentAclFilterFactoryTest {

    private final DocumentAclFilterFactory factory = new DocumentAclFilterFactory();

    @Test
    void buildsFailClosedAclFilterWithTenantCorpusAndVisibility() {
        Map<String, Object> filter = factory.build("policy_document", scope());

        assertThat(filter.toString())
                .contains("tenantId", "tenant-1")
                .contains("corpusId", "policy_document")
                .contains("status", "ACTIVE")
                .contains("visibility")
                .contains("departmentIds");
    }

    @Test
    void rejectsMissingAclScope() {
        assertThatThrownBy(() -> factory.build("policy_document", null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("ACL scope");
    }

    @Test
    void rejectsExpiredAclScope() {
        DocumentAclScope expired = new DocumentAclScope(
                "tenant-1",
                "user-1",
                List.of(),
                List.of(),
                List.of(),
                "acl-v1",
                Instant.now().minusSeconds(1));

        assertThatThrownBy(() -> factory.build("policy_document", expired))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("expired");
    }

    @Test
    void rejectsMissingTenantOrSnapshotVersionAtScopeBoundary() {
        assertThatThrownBy(() -> new DocumentAclScope(
                " ",
                "user-1",
                List.of(),
                List.of(),
                List.of(),
                "acl-v1",
                Instant.now().plusSeconds(60)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("tenantId");

        assertThatThrownBy(() -> new DocumentAclScope(
                "tenant-1",
                "user-1",
                List.of(),
                List.of(),
                List.of(),
                " ",
                Instant.now().plusSeconds(60)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("aclSnapshotVersion");
    }

    @Test
    void rejectsAclScopeWithTooManyVisibilityTerms() {
        DocumentAclScope oversized = new DocumentAclScope(
                "tenant-1",
                "user-1",
                IntStream.range(0, 128).mapToObj(index -> "dept-" + index).toList(),
                List.of(),
                List.of(),
                "acl-v1",
                Instant.now().plusSeconds(60));

        assertThatThrownBy(() -> factory.build("policy_document", oversized))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("max terms");
    }

    @Test
    void rejectsAclScopeWhenBaseVisibilityTermsPushTotalOverLimit() {
        DocumentAclScope oversized = new DocumentAclScope(
                "tenant-1",
                "user-1",
                IntStream.range(0, 126).mapToObj(index -> "dept-" + index).toList(),
                List.of(),
                List.of(),
                "acl-v1",
                Instant.now().plusSeconds(60));

        assertThatThrownBy(() -> factory.build("policy_document", oversized))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("max terms");
    }

    @Test
    void allowsAclScopeAtVisibilityTermLimit() {
        DocumentAclScope boundary = new DocumentAclScope(
                "tenant-1",
                "user-1",
                IntStream.range(0, 125).mapToObj(index -> "dept-" + index).toList(),
                List.of(),
                List.of(),
                "acl-v1",
                Instant.now().plusSeconds(60));

        Map<String, Object> filter = factory.build("policy_document", boundary);

        assertThat(filter.toString()).contains("dept-124");
    }

    private DocumentAclScope scope() {
        return new DocumentAclScope(
                "tenant-1",
                "user-1",
                List.of("dept-1"),
                List.of("role-1"),
                List.of("region:CN"),
                "acl-v1",
                Instant.now().plusSeconds(60));
    }
}
