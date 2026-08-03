package com.dylan.esquery.service;

import static com.dylan.esquery.KnowledgeTestProfiles.enabledProperties;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

import org.elasticsearch.client.RestClient;
import org.junit.jupiter.api.Test;

import com.dylan.esquery.api.knowledge.KnowledgeSearchRequest;
import com.dylan.esquery.api.knowledge.KnowledgeSearchResponse;
import com.dylan.esquery.config.KnowledgeSearchProperties;
import com.dylan.esquery.config.KnowledgeSearchProperties.KnowledgeSearchProfile;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeProviderException;
import com.fasterxml.jackson.databind.ObjectMapper;

class KnowledgeSearchServiceTest {
	private final ObjectMapper objectMapper = new ObjectMapper();
	private final KnowledgeSearchProperties properties = enabledProperties("0".repeat(64));
	private final KnowledgeSearchService service = new KnowledgeSearchService(null, objectMapper, properties);
	private final KnowledgeSearchProfile profile = properties.requireProfile("tax.policy", "tax-policy-v1");

	@Test
	void buildsOnlyProfileOwnedKeywordAndVectorQueries() {
		KnowledgeSearchRequest keyword = request("keyword", "政策", null, 5);
		Map<String, Object> keywordBody = service.buildSearchBody(keyword, profile);
		assertThat(keywordBody.toString()).contains("category", "policy", "title", "content");
		assertThat(keywordBody.toString()).doesNotContain("agent-doc-tax-policy-v2-read");

		KnowledgeSearchRequest vector = request("vector", null,
				java.util.Collections.nCopies(1024, 0.25d), 20);
		Map<String, Object> vectorBody = service.buildSearchBody(vector, profile);
		assertThat(vectorBody.toString()).contains("embedding", "num_candidates=100", "k=21");
	}

	@Test
	void mapsSortsHashesAndTruncatesValidatedCandidates() throws Exception {
		KnowledgeSearchRequest request = request("keyword", "政策", null, 1);
		byte[] responseBody = objectMapper.writeValueAsBytes(Map.of("hits", Map.of("hits", List.of(
				hit(0.5, "doc-2", "chunk-b", "正文二"),
				hit(0.9, "doc-1", "chunk-a", "正文一")))));

		KnowledgeSearchResponse response = service.decodeSearchResponse(responseBody, request, profile);
		assertThat(response.truncated()).isTrue();
		assertThat(response.candidates()).hasSize(1);
		assertThat(response.candidates().getFirst().chunkId()).isEqualTo("chunk-a");
		assertThat(response.candidates().getFirst().sourceRank()).isEqualTo(1);
		assertThat(response.candidates().getFirst().contentSha256()).matches("[0-9a-f]{64}");
	}

	@Test
	void rejectsDuplicateCandidateIdentityAndNonFiniteScore() throws Exception {
		KnowledgeSearchRequest request = request("keyword", "政策", null, 5);
		byte[] duplicates = objectMapper.writeValueAsBytes(Map.of("hits", Map.of("hits", List.of(
				hit(0.5, "doc", "chunk", "正文"), hit(0.4, "doc", "chunk", "正文")))));
		assertThatThrownBy(() -> service.decodeSearchResponse(duplicates, request, profile))
				.isInstanceOf(KnowledgeProviderException.class);

		byte[] nonFinite = "{\"hits\":{\"hits\":[{\"_score\":\"NaN\",\"_source\":{}}]}}"
				.getBytes(StandardCharsets.UTF_8);
		assertThatThrownBy(() -> service.decodeSearchResponse(nonFinite, request, profile))
				.isInstanceOf(KnowledgeProviderException.class);
	}

	@Test
	void mapsAnEmptyEsResponseToTheFiniteProviderFailure() throws Exception {
		RestClient restClient = mock(RestClient.class);
		when(restClient.performRequest(any())).thenReturn(null);
		KnowledgeSearchService liveService = new KnowledgeSearchService(restClient, objectMapper, properties);
		KnowledgeSearchRequest request = request("keyword", "政策", null, 5);
		KnowledgeReadDecision decision = new KnowledgeReadDecision("tax.policy", "tax-policy-v1",
				profile.getProfileVersion(), profile.getReadPolicyVersion(), "decision");

		assertThatThrownBy(() -> liveService.search(request, decision))
				.isInstanceOf(KnowledgeProviderException.class);
	}

	private static KnowledgeSearchRequest request(String path, String text, List<Double> vector, int limit) {
		return new KnowledgeSearchRequest(1, "tax.policy", "tax-policy-v1", path, text, vector, limit);
	}

	private static Map<String, Object> hit(double score, String documentId, String chunkId, String content) {
		return Map.of("_score", score, "_source", Map.of(
				"document_id", documentId,
				"chunk_id", chunkId,
				"title", "标题",
				"content", content,
				"source_url", "/source",
				"document_number", "文号",
				"written_date", "2025-01-01",
				"material_type", "tax_policy",
				"policy_ref", "policy-1"));
	}
}
