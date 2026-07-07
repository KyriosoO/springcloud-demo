package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.AdapterDocumentEvidence;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentEvidencePreSecurityFilterTest {

    private static final Instant NOW = Instant.now().plusSeconds(300);

    @Test
    void rejectsEvidenceWhenReadableTextFieldsAreMissing() {
        var filtered = new DocumentEvidencePreSecurityFilter().filter(
                List.of(evidence()),
                scope(Set.of("title", "sourceType")),
                "policy_document");

        assertThat(filtered).isEmpty();
    }

    @Test
    void keepsOnlySnippetWhenContentIsNotReadable() {
        var filtered = new DocumentEvidencePreSecurityFilter().filter(
                List.of(evidence()),
                scope(Set.of("title", "sourceUri", "snippet")),
                "policy_document");

        assertThat(filtered).singleElement().satisfies(item -> {
            assertThat(item.getSnippet()).isEqualTo("授权摘要片段");
            assertThat(item.getContent()).isNull();
            assertThat(item.getContextBefore()).isNull();
            assertThat(item.getContextAfter()).isNull();
            assertThat(item.getTitle()).isEqualTo("休假政策");
            assertThat(item.getSourceUri()).isEqualTo("https://docs.example/policy.pdf");
            assertThat(item.getMetadata()).isNull();
        });
    }

    @Test
    void keepsContentAndContextOnlyWhenContentIsReadable() {
        var filtered = new DocumentEvidencePreSecurityFilter().filter(
                List.of(evidence()),
                scope(Set.of("content", "snippet")),
                "policy_document");

        assertThat(filtered).singleElement().satisfies(item -> {
            assertThat(item.getContent()).isEqualTo("完整正文不应在缺少 content 权限时进入 LLM");
            assertThat(item.getContextBefore()).containsExactly("上文");
            assertThat(item.getContextAfter()).containsExactly("下文");
            assertThat(item.getTitle()).isNull();
            assertThat(item.getMetadata()).isNull();
        });
    }

    private static AdapterDocumentEvidence evidence() {
        AdapterDocumentEvidence evidence = new AdapterDocumentEvidence();
        evidence.setDocumentId("doc-1");
        evidence.setChunkId("chunk-1");
        evidence.setTitle("休假政策");
        evidence.setSourceType("policy");
        evidence.setSection("年假");
        evidence.setPage(3);
        evidence.setSourceUri("https://docs.example/policy.pdf?token=secret#page=3");
        evidence.setSnippet("授权摘要片段");
        evidence.setContent("完整正文不应在缺少 content 权限时进入 LLM");
        evidence.setContextBefore(List.of("上文"));
        evidence.setContextAfter(List.of("下文"));
        evidence.setMetadata(Map.of("embedding", List.of(0.1, 0.2), "aclRef", "acl-1"));
        return evidence;
    }

    private static ExecutionScope scope(Set<String> allowedFields) {
        return new ExecutionScope(
                "user:u-1",
                new DomainMetadataEvidence("catalog-v1", "adapter-v1", "availability", NOW),
                NOW,
                "perm-evidence",
                "perm-v1",
                "policy-v1",
                Set.of("document.answer"),
                Set.of("policy_document"),
                Map.of("policy_document", allowedFields),
                Map.of(),
                Duration.ofSeconds(30),
                1,
                20,
                1024 * 1024);
    }
}
