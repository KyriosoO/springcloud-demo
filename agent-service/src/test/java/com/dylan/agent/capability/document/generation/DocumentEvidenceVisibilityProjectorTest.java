package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;
import com.dylan.agent.capability.document.evidence.DocumentEvidenceVisibilityProjector;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentEvidenceVisibilityProjectorTest {

    private static final Instant NOW = Instant.now().plusSeconds(300);

    @Test
    void rejectsMissingExecutionScope() {
        assertThatThrownBy(() -> new DocumentEvidenceVisibilityProjector().project(
                List.of(evidence()), null, "policy_document"))
                .isInstanceOf(NullPointerException.class)
                .hasMessageContaining("executionScope");
    }

    @Test
    void rejectsEvidenceWhenReadableTextFieldsAreMissing() {
        var filtered = new DocumentEvidenceVisibilityProjector().project(
                List.of(evidence()),
                scope(Set.of("title", "sourceType")),
                "policy_document");

        assertThat(filtered).isEmpty();
    }

    @Test
    void keepsOnlySnippetWhenContentIsNotReadable() {
        var filtered = new DocumentEvidenceVisibilityProjector().project(
                List.of(evidence()),
                scope(Set.of("title", "sourceUri", "snippet")),
                "policy_document");

        assertThat(filtered).singleElement().satisfies(item -> {
            assertThat(item.snippet()).isEqualTo("授权摘要片段");
            assertThat(item.content()).isNull();
            assertThat(item.contextBefore()).isEmpty();
            assertThat(item.contextAfter()).isEmpty();
            assertThat(item.title()).isEqualTo("休假政策");
            assertThat(item.sourceUri()).isEqualTo("https://docs.example/policy.pdf");
            assertThat(item.safeFieldNames()).isEmpty();
        });
    }

    @Test
    void keepsContentAndContextOnlyWhenContentIsReadable() {
        var filtered = new DocumentEvidenceVisibilityProjector().project(
                List.of(evidence()),
                scope(Set.of("content", "snippet")),
                "policy_document");

        assertThat(filtered).singleElement().satisfies(item -> {
            assertThat(item.content()).isEqualTo("完整正文不应在缺少 content 权限时进入 LLM");
            assertThat(item.contextBefore()).containsExactly("上文");
            assertThat(item.contextAfter()).containsExactly("下文");
            assertThat(item.title()).isNull();
            assertThat(item.safeFieldNames()).isEmpty();
        });
    }

    private static AclBoundDocumentHit evidence() {
        return DocumentEvidenceTestFixtures.evidence(
                "休假政策", "年假", 3, "https://docs.example/policy.pdf?token=secret#page=3",
                "授权摘要片段", "完整正文不应在缺少 content 权限时进入 LLM", null,
                List.of("上文"), List.of("下文"), 0, null);
    }

    private static ExecutionScope scope(Set<String> allowedFields) {
        return com.dylan.agent.testsupport.ExecutionScopeTestFactory.create(
                "user:u-1",
                com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence("catalog-v1", "adapter-v1", "availability", NOW),
                NOW,
                "perm-evidence",
                "perm-v1",
                "policy-v1",
                Set.of("document.answer"),
                Set.of("policy_document"),
                Map.of("policy_document", allowedFields),
                Map.of(),
                com.dylan.agent.kernel.resource.StandardResourceLimits
                        .testEffective(20, 20, 1024 * 1024));
    }
}
