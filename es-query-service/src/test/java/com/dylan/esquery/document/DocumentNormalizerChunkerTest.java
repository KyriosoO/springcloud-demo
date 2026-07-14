package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentSchemaRefDto;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentNormalizerChunkerTest {
    private final DocumentCorpusDefinition corpus = new DocumentCorpusDefinition(
            new DocumentCorpusKeyDto("policy", "document"), "agent-doc-policy-document-read",
            new DocumentSchemaRefDto("document", "3", "a".repeat(64)), "standard", "disabled",
            "char-window-v3", "connector-v1", Set.of("category"));

    @Test
    void canonicalizesTextUriAclAndProducesStableChunks() {
        SourceDocument source = source("  第一段\r\n\t第二段  ", "https://Example.com/policy?a=1#part");
        DocumentNormalizer normalizer = new DocumentNormalizer(100);
        NormalizedDocument normalized = normalizer.normalize(source, corpus);

        assertThat(normalized.content()).isEqualTo("第一段\n第二段");
        assertThat(normalized.safeSourceUri()).isEqualTo("https://example.com/policy");
        assertThat(normalized.userIds()).containsExactly("u-1", "u-2");

        DocumentChunker chunker = new DocumentChunker(4, 1);
        List<NormalizedDocumentChunk> first = chunker.chunk(normalized, corpus.chunkStrategyRef());
        List<NormalizedDocumentChunk> second = chunker.chunk(normalized, corpus.chunkStrategyRef());
        assertThat(first).isEqualTo(second);
        assertThat(first).hasSizeGreaterThan(1);
        assertThat(first).allSatisfy(chunk -> {
            assertThat(chunk.chunkId()).matches("[A-Za-z0-9_-]{43}");
            assertThat(chunk.chunkContentHash()).matches("[0-9a-f]{64}");
            assertThat(chunk.charStart()).isLessThan(chunk.charEnd());
        });
    }

    @Test
    void rejectsAclLeakAndDocumentLevelEmbedding() {
        DocumentNormalizer normalizer = new DocumentNormalizer(100);
        SourceDocument aclLeak = new SourceDocument("tenant", "doc", "v1", "text", null, null, null,
                null, Instant.EPOCH, "ACTIVE", "acl", "v1", "USER", List.of("u-1"),
                List.of("d-1"), List.of(), List.of(), List.of(), List.of());
        assertThatThrownBy(() -> normalizer.normalize(aclLeak, corpus)).hasMessageContaining("unrelated principals");
        assertThatThrownBy(() -> normalizer.normalize(withEmbedding(source("text", null)), corpus))
                .hasMessageContaining("must not supply");
    }

    private static SourceDocument source(String content, String uri) {
        return new SourceDocument("tenant", "doc", "v1", content, "title", null, null, uri,
                Instant.parse("2026-07-14T00:00:00Z"), "ACTIVE", "acl", "v1", "USER",
                List.of("u-2", "u-1"), List.of(), List.of(), List.of(),
                List.of(new DocumentBusinessFieldValue.Keyword("category", "policy")), List.of());
    }

    private static SourceDocument withEmbedding(SourceDocument value) {
        return new SourceDocument(value.tenantId(), value.documentId(), value.documentVersion(), value.content(),
                value.title(), value.section(), value.page(), value.sourceUri(), value.sourceUpdatedAt(), value.status(),
                value.aclRef(), value.aclVersion(), value.visibility(), value.userIds(), value.departmentIds(),
                value.roleIds(), value.attributeKeys(), value.businessFields(), List.of(1.0));
    }
}
