package com.dylan.esquery.service;

import static com.dylan.esquery.KnowledgeTestProfiles.enabledProperties;
import static com.dylan.esquery.KnowledgeTestProfiles.defaultSourceFields;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.apache.http.entity.ContentType;
import org.apache.http.nio.entity.NStringEntity;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestClient;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

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

	@Test
	void rejectsDuplicateAndTrailingEsJson() {
		KnowledgeSearchRequest request = request("keyword", "政策", null, 5);
		byte[] duplicate = "{\"hits\":{\"hits\":[]},\"hits\":{\"hits\":[]}}"
				.getBytes(StandardCharsets.UTF_8);
		byte[] trailing = "{\"hits\":{\"hits\":[]}} {}".getBytes(StandardCharsets.UTF_8);
		assertThatThrownBy(() -> service.decodeSearchResponse(duplicate, request, profile))
				.isInstanceOf(KnowledgeProviderException.class);
		assertThatThrownBy(() -> service.decodeSearchResponse(trailing, request, profile))
				.isInstanceOf(KnowledgeProviderException.class);
	}

	@Test
	void mapsConfiguredNestedSourceFieldsWithoutAcceptingUnknownSiblings() throws Exception {
		Map<String, String> sourceFields = new LinkedHashMap<>(defaultSourceFields());
		sourceFields.put("document-id", "identity.document_id");
		KnowledgeSearchProperties nestedProperties = enabledProperties("0".repeat(64), sourceFields);
		KnowledgeSearchProfile nestedProfile = nestedProperties.requireProfile("tax.policy", "tax-policy-v1");
		KnowledgeSearchService nestedService = new KnowledgeSearchService(null, objectMapper, nestedProperties);
		Map<String, Object> nestedHit = new LinkedHashMap<>(hit(0.5, "doc", "chunk", "正文"));
		@SuppressWarnings("unchecked")
		Map<String, Object> source = new LinkedHashMap<>((Map<String, Object>) nestedHit.get("_source"));
		source.remove("document_id");
		source.put("identity", Map.of("document_id", "doc"));
		nestedHit.put("_source", source);
		byte[] valid = objectMapper.writeValueAsBytes(Map.of("hits", Map.of("hits", List.of(nestedHit))));
		assertThat(nestedService.decodeSearchResponse(valid,
				request("keyword", "政策", null, 5), nestedProfile).candidates())
				.singleElement().extracting(candidate -> candidate.documentId()).isEqualTo("doc");

		source.put("identity", Map.of("document_id", "doc", "unknown", "value"));
		byte[] unknown = objectMapper.writeValueAsBytes(Map.of("hits", Map.of("hits", List.of(nestedHit))));
		assertThatThrownBy(() -> nestedService.decodeSearchResponse(unknown,
				request("keyword", "政策", null, 5), nestedProfile))
				.isInstanceOf(KnowledgeProviderException.class);
	}

	@Test
	void requestsIdentityEncodingAndRejectsCompressedResponses() throws Exception {
		RestClient restClient = mock(RestClient.class);
		Response identityResponse = response("{\"hits\":{\"hits\":[]}}",
				"application/json; charset=UTF-8", null);
		when(restClient.performRequest(any())).thenReturn(identityResponse);
		KnowledgeSearchService liveService = new KnowledgeSearchService(restClient, objectMapper, properties);
		KnowledgeReadDecision decision = decision();
		assertThat(liveService.search(request("keyword", "政策", null, 5), decision).candidates()).isEmpty();
		ArgumentCaptor<Request> requestCaptor = ArgumentCaptor.forClass(Request.class);
		org.mockito.Mockito.verify(restClient).performRequest(requestCaptor.capture());
		assertThat(requestCaptor.getValue().getOptions().getHeaders())
				.anySatisfy(header -> {
					assertThat(header.getName()).isEqualToIgnoringCase("Accept-Encoding");
					assertThat(header.getValue()).isEqualTo("identity");
				});

		RestClient compressedClient = mock(RestClient.class);
		Response compressedResponse = response("{\"hits\":{\"hits\":[]}}",
				"application/json", "gzip");
		when(compressedClient.performRequest(any())).thenReturn(compressedResponse);
		KnowledgeSearchService compressedService = new KnowledgeSearchService(
				compressedClient, objectMapper, properties);
		assertThatThrownBy(() -> compressedService.search(
				request("keyword", "政策", null, 5), decision))
				.isInstanceOf(KnowledgeProviderException.class);
	}

	private static KnowledgeSearchRequest request(String path, String text, List<Double> vector, int limit) {
		return new KnowledgeSearchRequest(1, "tax.policy", "tax-policy-v1", path, text, vector, limit);
	}

	private KnowledgeReadDecision decision() {
		return new KnowledgeReadDecision("tax.policy", "tax-policy-v1",
				profile.getProfileVersion(), profile.getReadPolicyVersion(), "decision");
	}

	private static Response response(String json, String contentType, String contentEncoding) throws Exception {
		Response response = mock(Response.class);
		when(response.getEntity()).thenReturn(new NStringEntity(json, ContentType.APPLICATION_JSON));
		when(response.getHeader("Content-Type")).thenReturn(contentType);
		when(response.getHeader("Content-Encoding")).thenReturn(contentEncoding);
		return response;
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
