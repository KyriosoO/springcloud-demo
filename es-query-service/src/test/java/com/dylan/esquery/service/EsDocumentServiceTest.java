package com.dylan.esquery.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import com.dylan.esquery.api.model.HybridContextWindow;
import com.dylan.esquery.api.model.HybridSearchRequest;
import com.dylan.esquery.api.model.VectorSearchRequest;
import com.dylan.esquery.config.EsQueryProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.apache.http.HttpEntity;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestClient;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class EsDocumentServiceTest {

	private final ObjectMapper objectMapper = new ObjectMapper();
	private EsDocumentService service;

	@BeforeEach
	void setUp() {
		EsQueryProperties properties = new EsQueryProperties();
		properties.setTotalHitsThreshold(10000);
		properties.setDocumentSourceAllowedHosts(List.of("document-platform"));
		properties.afterPropertiesSet();
		service = new EsDocumentService(null, objectMapper, properties);
	}

	@Test
	void searchAddsConfiguredThresholdWhenCallerOmitsTrackTotalHits() throws Exception {
		JsonNode body = objectMapper.readTree(service.applyDefaultTrackTotalHits("""
				{"query":{"match_all":{}}}
				"""));

		assertThat(body.path("track_total_hits").asInt()).isEqualTo(10000);
	}

	@Test
	void searchKeepsCallerBooleanTrackTotalHits() throws Exception {
		JsonNode body = objectMapper.readTree(service.applyDefaultTrackTotalHits("""
				{"track_total_hits":true,"query":{"match_all":{}}}
				"""));

		assertThat(body.path("track_total_hits").asBoolean()).isTrue();
	}

	@Test
	void searchKeepsCallerDisabledTrackTotalHits() throws Exception {
		JsonNode body = objectMapper.readTree(service.applyDefaultTrackTotalHits("""
				{"track_total_hits":false,"query":{"match_all":{}}}
				"""));

		assertThat(body.path("track_total_hits").asBoolean()).isFalse();
	}

	@Test
	void searchKeepsCallerNumericTrackTotalHits() throws Exception {
		JsonNode body = objectMapper.readTree(service.applyDefaultTrackTotalHits("""
				{"track_total_hits":2500,"query":{"match_all":{}}}
				"""));

		assertThat(body.path("track_total_hits").asInt()).isEqualTo(2500);
	}

	@Test
	void searchRejectsNonObjectDsl() {
		assertThatThrownBy(() -> service.applyDefaultTrackTotalHits("[]"))
				.isInstanceOf(IllegalArgumentException.class)
				.hasMessageContaining("JSON object");
	}

	@Test
	void vectorSearchUsesCallerThresholdWhenPresent() {
		assertThat(service.resolveTrackTotalHits(500)).isEqualTo(500);
		assertThat(service.resolveTrackTotalHits(null)).isEqualTo(10000);
	}

	@Test
	void vectorSearchRejectsNonPositiveThreshold() {
		assertThatThrownBy(() -> service.resolveTrackTotalHits(0))
				.isInstanceOf(IllegalArgumentException.class)
				.hasMessageContaining("greater than 0");
	}

	@Test
	void vectorSearchBodyIncludesCallerFilterDsl() {
		VectorSearchRequest request = new VectorSearchRequest();
		request.setQueryVector(List.of(0.1, 0.2));
		request.setFilterDsl(Map.of("bool", Map.of("filter", List.of(Map.of("term", Map.of("sourceType", "policy"))))));

		Map<String, Object> body = service.vectorSearchBody(request);

		@SuppressWarnings("unchecked")
		Map<String, Object> knn = (Map<String, Object>) body.get("knn");
		assertThat(knn.get("filter").toString()).contains("sourceType", "policy");
		assertThat(body.get("_source").toString()).contains("embedding");
	}

	@Test
	void vectorSearchRejectsMissingFilterForDocumentIndex() {
		VectorSearchRequest request = new VectorSearchRequest();
		request.setQueryVector(List.of(0.1, 0.2));

		assertThatThrownBy(() -> service.vectorSearchBody("agent-doc-policy", request))
				.isInstanceOf(IllegalArgumentException.class)
				.hasMessageContaining("ACL filterDsl");
	}

	@Test
	void hybridSearchRejectsMissingVector() {
		HybridSearchRequest request = new HybridSearchRequest();
		request.setKeywordDsl(Map.of("query", Map.of("match_all", Map.of())));

		assertThatThrownBy(() -> service.validateHybridRequest(request))
				.isInstanceOf(IllegalArgumentException.class)
				.hasMessageContaining("queryVector");
	}

	@Test
	void hybridKeywordBodyOverridesKeywordCandidateSize() {
		HybridSearchRequest request = new HybridSearchRequest();
		request.setKeywordDsl(Map.of("query", Map.of("match_all", Map.of()), "size", 99));
		request.setKeywordK(12);
		request.setQueryVector(List.of(0.1, 0.2));

		Map<String, Object> body = service.keywordSearchBody(request);

		assertThat(body.get("size")).isEqualTo(12);
		assertThat(body.get("track_total_hits")).isEqualTo(10000);
	}

	@Test
	void hybridKeywordBodyMergesRequestFilters() {
		HybridSearchRequest request = new HybridSearchRequest();
		request.setKeywordDsl(Map.of("query", Map.of("match_all", Map.of())));
		request.setFilters(Map.of("bool", Map.of("filter", List.of(
				Map.of("term", Map.of("tenantId", "tenant-1")),
				Map.of("term", Map.of("corpusId", "policy_document"))))));
		request.setQueryVector(List.of(0.1, 0.2));

		Map<String, Object> body = service.keywordSearchBody(request);

		assertThat(body.get("query").toString()).contains("tenantId", "tenant-1", "corpusId");
	}

	@Test
	void hybridKeywordBodyAppliesSourceExcludes() {
		HybridSearchRequest request = new HybridSearchRequest();
		request.setKeywordDsl(Map.of("query", Map.of("match_all", Map.of())));
		request.setSourceExcludes(List.of("embedding", "rawContent"));
		request.setQueryVector(List.of(0.1, 0.2));

		Map<String, Object> body = service.keywordSearchBody(request);

		assertThat(body.get("_source").toString()).contains("embedding", "rawContent");
	}

	@Test
	void hybridSearchRejectsMissingFiltersForDocumentIndex() {
		HybridSearchRequest request = new HybridSearchRequest();
		request.setKeywordDsl(Map.of("query", Map.of("match_all", Map.of())));
		request.setQueryVector(List.of(0.1, 0.2));

		assertThatThrownBy(() -> service.validateHybridRequest("agent-doc-policy", request))
				.isInstanceOf(IllegalArgumentException.class)
				.hasMessageContaining("ACL filters");
	}

	@Test
	void hybridSearchAppliesSourceExcludesToKeywordAndVectorRequests() throws Exception {
		RestClient restClient = mock(RestClient.class);
		Response keywordResponse = response("""
				{"hits":{"hits":[{"_id":"doc-1","_score":1.0,"_source":{"documentId":"doc-1","chunkId":"chunk-1"}}]}}
				""");
		Response vectorResponse = response("""
				{"hits":{"hits":[{"_id":"doc-1","_score":0.9,"_source":{"documentId":"doc-1","chunkId":"chunk-1"}}]}}
				""");
		when(restClient.performRequest(any())).thenReturn(keywordResponse, vectorResponse);
		EsDocumentService searchService = new EsDocumentService(restClient, objectMapper, properties());
		HybridSearchRequest request = new HybridSearchRequest();
		request.setKeywordDsl(Map.of("query", Map.of("match_all", Map.of())));
		request.setFilters(Map.of("bool", Map.of("filter", List.of(Map.of("term", Map.of("tenantId", "tenant-1"))))));
		request.setQueryVector(List.of(0.1, 0.2));
		request.setSourceExcludes(List.of("embedding"));

		searchService.hybridSearch("agent-doc-policy", request);

		ArgumentCaptor<org.elasticsearch.client.Request> captor =
				ArgumentCaptor.forClass(org.elasticsearch.client.Request.class);
		verify(restClient, times(2)).performRequest(captor.capture());
		String keywordBody = body(captor.getAllValues().get(0));
		String vectorBody = body(captor.getAllValues().get(1));
		assertThat(keywordBody).contains("\"_source\":{\"excludes\":[\"embedding\"]}");
		assertThat(vectorBody).contains("\"_source\":{\"excludes\":[\"embedding\"]}");
	}

	@Test
	void hybridSearchEnrichesContextWindowWithSameDocumentAdjacentChunks() throws Exception {
		RestClient restClient = mock(RestClient.class);
		Response keywordResponse = response("""
				{"hits":{"hits":[{"_id":"chunk-1","_score":1.0,"_source":{"documentId":"doc-1","chunkId":"chunk-1","chunkIndex":1,"content":"命中文本"}}]}}
				""");
		Response vectorResponse = response("""
				{"hits":{"hits":[{"_id":"chunk-1","_score":0.9,"_source":{"documentId":"doc-1","chunkId":"chunk-1","chunkIndex":1,"content":"命中文本"}}]}}
				""");
		Response contextResponse = response("""
				{"hits":{"hits":[
				  {"_id":"chunk-0","_source":{"documentId":"doc-1","chunkId":"chunk-0","chunkIndex":0,"content":"上一段"}},
				  {"_id":"chunk-2","_source":{"documentId":"doc-1","chunkId":"chunk-2","chunkIndex":2,"content":"下一段"}}
				]}}
				""");
		when(restClient.performRequest(any())).thenReturn(keywordResponse, vectorResponse, contextResponse);
		EsDocumentService searchService = new EsDocumentService(restClient, objectMapper, properties());
		HybridSearchRequest request = new HybridSearchRequest();
		request.setKeywordDsl(Map.of("query", Map.of("match_all", Map.of())));
		request.setFilters(Map.of("bool", Map.of("filter", List.of(Map.of("term", Map.of("tenantId", "tenant-1"))))));
		request.setQueryVector(List.of(0.1, 0.2));
		request.setSourceExcludes(List.of("embedding"));
		HybridContextWindow contextWindow = new HybridContextWindow();
		contextWindow.setBeforeChunks(1);
		contextWindow.setAfterChunks(1);
		contextWindow.setMaxContextChars(100);
		request.setContextWindow(contextWindow);

		var response = searchService.hybridSearch("agent-doc-policy", request);

		assertThat(response.getHits()).hasSize(1);
		assertThat(response.getHits().get(0).getContextBefore()).containsExactly("上一段");
		assertThat(response.getHits().get(0).getContextAfter()).containsExactly("下一段");
		ArgumentCaptor<org.elasticsearch.client.Request> captor =
				ArgumentCaptor.forClass(org.elasticsearch.client.Request.class);
		verify(restClient, times(3)).performRequest(captor.capture());
		String contextBody = body(captor.getAllValues().get(2));
		assertThat(contextBody).contains("tenantId", "tenant-1", "documentId", "doc-1", "chunkIndex", "0", "2");
	}

	@Test
	void hybridSearchRejectsNegativeContextWindow() {
		HybridSearchRequest request = new HybridSearchRequest();
		request.setKeywordDsl(Map.of("query", Map.of("match_all", Map.of())));
		request.setQueryVector(List.of(0.1, 0.2));
		HybridContextWindow contextWindow = new HybridContextWindow();
		contextWindow.setBeforeChunks(-1);
		request.setContextWindow(contextWindow);

		assertThatThrownBy(() -> service.validateHybridRequest(request))
				.isInstanceOf(IllegalArgumentException.class)
				.hasMessageContaining("beforeChunks");
	}

	private EsQueryProperties properties() {
		EsQueryProperties properties = new EsQueryProperties();
		properties.setTotalHitsThreshold(10000);
		properties.setDocumentSourceAllowedHosts(List.of("document-platform"));
		properties.afterPropertiesSet();
		return properties;
	}

	private Response response(String body) throws Exception {
		Response response = mock(Response.class);
		HttpEntity entity = mock(HttpEntity.class);
		when(entity.getContent()).thenReturn(new java.io.ByteArrayInputStream(body.getBytes(StandardCharsets.UTF_8)));
		when(response.getEntity()).thenReturn(entity);
		return response;
	}

	private String body(org.elasticsearch.client.Request request) throws Exception {
		return new String(request.getEntity().getContent().readAllBytes(), StandardCharsets.UTF_8);
	}
}
