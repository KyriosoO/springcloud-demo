package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.adapter.api.document.DocumentAclScope;
import com.dylan.agent.adapter.api.document.DocumentHybridOptions;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.plan.DocumentRetrievalMode;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentRetrievalMapperTest {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final DocumentRetrievalMapper mapper = new DocumentRetrievalMapper(objectMapper);

    @Test
    void mapsContainsAnyToShouldMatchClauses() throws Exception {
        JsonNode root = objectMapper.readTree(mapper.toSearchDsl(request(
                new ValidatedFilter("sourceType", AgentOperator.CONTAINS_ANY, null, List.of("policy", "guide")))));

        assertThat(root.path("_source").path("excludes").get(0).asText()).isEqualTo("embedding");
        JsonNode filter = root.path("query").path("bool").path("filter").get(0);
        assertThat(filter.path("bool").path("minimum_should_match").asInt()).isEqualTo(1);
        assertThat(filter.path("bool").path("should").get(0).path("match").path("sourceType").asText())
                .isEqualTo("policy");
        assertThat(filter.path("bool").path("should").get(1).path("match").path("sourceType").asText())
                .isEqualTo("guide");
    }

    @Test
    void mapsStartsWithAnyToShouldPrefixClauses() throws Exception {
        JsonNode root = objectMapper.readTree(mapper.toSearchDsl(request(
                new ValidatedFilter("title", AgentOperator.STARTS_WITH_ANY, null, List.of("制度", "规范")))));

        JsonNode filter = root.path("query").path("bool").path("filter").get(0);
        assertThat(filter.path("bool").path("minimum_should_match").asInt()).isEqualTo(1);
        assertThat(filter.path("bool").path("should").get(0).path("prefix").path("title").asText())
                .isEqualTo("制度");
        assertThat(filter.path("bool").path("should").get(1).path("prefix").path("title").asText())
                .isEqualTo("规范");
    }

    @Test
    void mapsTextKeywordFieldEqToKeywordSubField() throws Exception {
        JsonNode root = objectMapper.readTree(mapper.toSearchDsl(request(
                new ValidatedFilter("section", AgentOperator.EQ, "税收政策-增值税", List.of()))));

        JsonNode filter = root.path("query").path("bool").path("filter").get(0);
        assertThat(filter.path("term").path("section.keyword").asText())
                .isEqualTo("税收政策-增值税");
    }

    @Test
    void keywordDslIncludesDerivedEvidenceTextFields() throws Exception {
        JsonNode root = objectMapper.readTree(mapper.toSearchDsl(request(
                new ValidatedFilter("sourceType", AgentOperator.EQ, "policy", List.of()))));

        JsonNode fields = root.path("query").path("bool").path("must").get(0)
                .path("multi_match").path("fields");
        List<String> fieldNames = new ArrayList<>();
        fields.forEach(field -> fieldNames.add(field.asText()));
        assertThat(fieldNames)
                .contains("generationText", "citationText^1.2");
    }

    @Test
    void mapsLiteratureAuthorEqToKeywordSubField() throws Exception {
        JsonNode root = objectMapper.readTree(mapper.toSearchDsl(request(
                new ValidatedFilter("author", AgentOperator.EQ, "鲁迅", List.of()))));

        JsonNode filter = root.path("query").path("bool").path("filter").get(0);
        assertThat(filter.path("term").path("author.keyword").asText())
                .isEqualTo("鲁迅");
    }

    @Test
    void mapsHybridRequestWithKeywordDslAndVector() {
        DocumentRetrievalRequest request = new DocumentRetrievalRequest(
                DocumentPlanOperation.ANSWER,
                "policy_document",
                "tax_policy",
                "tax-v2",
                "v2",
                "agent-doc-tax-policy-read",
                "休假政策",
                List.of(),
                List.of(),
                List.of(new ValidatedFilter("sourceType", AgentOperator.EQ, "policy", List.of())),
                List.of(),
                5,
                1,
                5,
                null,
                true,
                DocumentRetrievalMode.HYBRID,
                List.of(0.1, 0.2),
                new DocumentHybridOptions(10, 12, 60, 100),
                null,
                null).withAclScope(scope(), "perm-evidence", "perm-v1");

        var hybrid = mapper.toHybridRequest(request);

        assertThat(hybrid.getQueryText()).isEqualTo("休假政策");
        assertThat(hybrid.getQueryVector()).containsExactly(0.1, 0.2);
        assertThat(hybrid.getKeywordK()).isEqualTo(10);
        assertThat(hybrid.getVectorK()).isEqualTo(12);
        assertThat(hybrid.getKeywordDsl()).containsKey("query");
        assertThat(hybrid.getKeywordDsl().toString()).contains("embedding");
        assertThat(hybrid.getKeywordDsl().toString()).doesNotContain("tenantId", "sourceType");
        assertThat(hybrid.getFilters()).isNotNull();
        assertThat(hybrid.getFilters().toString()).contains("sourceType", "policy");
        assertThat(hybrid.getFilters().toString()).contains("tenantId", "tenant-1", "materialType", "tax_policy", "retrievalProfile", "tax-v2");
        assertThat(hybrid.getPermissionEvidenceId()).isEqualTo("perm-evidence");
        assertThat(hybrid.getPermissionVersion()).isEqualTo("perm-v1");
        assertThat(hybrid.getFilterDigest()).startsWith("sha256:");
        assertThat(hybrid.getSourceExcludes()).containsExactly("embedding", "embeddingText");
    }

    @Test
    void mapsProfileAndMultiChannelHybridRequest() {
        DocumentHybridOptions hybridOptions = new DocumentHybridOptions(
                10,
                12,
                60,
                100,
                3,
                4,
                2,
                List.of("BM25", "EXACT", "PHRASE", "DENSE_VECTOR"),
                Map.of("BM25", 2.0d),
                "embedding_v2",
                true,
                20);
        DocumentRetrievalRequest request = new DocumentRetrievalRequest(
                DocumentPlanOperation.ANSWER,
                "policy_document",
                "tax_policy",
                "tax-v2",
                "v2",
                "agent-doc-tax-policy-read",
                "财税〔2026〕1号",
                List.of("增值税"),
                List.of("小规模纳税人增值税优惠"),
                List.of(new ValidatedFilter("sourceType", AgentOperator.EQ, "policy", List.of())),
                List.of(),
                5,
                1,
                5,
                null,
                true,
                DocumentRetrievalMode.HYBRID,
                List.of(0.1, 0.2),
                hybridOptions,
                null,
                null).withAclScope(scope(), "perm-evidence", "perm-v1");

        var hybrid = mapper.toHybridRequest(request);

        assertThat(hybrid.getMaterialType()).isEqualTo("tax_policy");
        assertThat(hybrid.getRetrievalProfile()).isEqualTo("tax-v2");
        assertThat(hybrid.getProfileVersion()).isEqualTo("v2");
        assertThat(hybrid.getIndexAlias()).isEqualTo("agent-doc-tax-policy-read");
        assertThat(hybrid.getPermissionEvidenceId()).isEqualTo("perm-evidence");
        assertThat(hybrid.getPermissionVersion()).isEqualTo("perm-v1");
        assertThat(hybrid.getFilterDigest()).startsWith("sha256:");
        assertThat(hybrid.getMaxChunksPerDocument()).isEqualTo(2);
        assertThat(hybrid.getChannelWeights()).containsEntry("BM25", 2.0d);
        assertThat(hybrid.getChannels()).hasSize(4);
        assertThat(hybrid.getChannels()).extracting(channel -> channel.getChannel())
                .containsExactly("BM25", "EXACT", "PHRASE", "DENSE_VECTOR");
        assertThat(hybrid.getChannels().get(1).getQueryDsl().toString())
                .contains("title.keyword", "documentNo", "issuer", "增值税")
                .doesNotContain("documentNumber", "issuingAuthority");
        assertThat(hybrid.getChannels().get(2).getQueryDsl().toString())
                .contains("match_phrase", "小规模纳税人增值税优惠");
        assertThat(hybrid.getChannels().get(3).getEmbeddingField()).isEqualTo("embedding_v2");
        assertThat(hybrid.getChannels().get(3).getQueryVector()).containsExactly(0.1, 0.2);
    }

    @Test
    void mapsVectorRequestWithFilterDsl() {
        DocumentRetrievalRequest request = new DocumentRetrievalRequest(
                DocumentPlanOperation.ANSWER,
                "policy_document",
                "tax_policy",
                "tax-v2",
                "v2",
                "agent-doc-tax-policy-read",
                "休假政策",
                List.of(),
                List.of(),
                List.of(new ValidatedFilter("sourceType", AgentOperator.EQ, "policy", List.of())),
                List.of(),
                5,
                1,
                5,
                null,
                true,
                DocumentRetrievalMode.VECTOR,
                List.of(0.1, 0.2),
                new DocumentHybridOptions(10, 12, 60, 100),
                null,
                null).withAclScope(scope(), "perm-evidence", "perm-v1");

        var vector = mapper.toVectorRequest(request);

        assertThat(vector.getQueryVector()).containsExactly(0.1, 0.2);
        assertThat(vector.getFilterDsl()).isNotNull();
        assertThat(vector.getFilterDsl().toString()).contains("sourceType", "policy");
        assertThat(vector.getFilterDsl().toString()).contains("tenantId", "tenant-1", "materialType", "tax_policy", "retrievalProfile", "tax-v2");
    }

    private DocumentRetrievalRequest request(ValidatedFilter filter) {
        return new DocumentRetrievalRequest(
                DocumentPlanOperation.SEARCH,
                "policy_document",
                "tax_policy",
                "tax-v2",
                "v2",
                "agent-doc-tax-policy-read",
                "休假政策",
                List.of(),
                List.of(),
                List.of(filter),
                List.of(),
                5,
                1,
                5,
                null,
                false,
                DocumentRetrievalMode.KEYWORD,
                List.of(),
                null,
                null,
                null).withAclScope(scope(), "perm-evidence", "perm-v1");
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
