package com.dylan.esquery.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import com.dylan.esquery.api.model.HybridSearchRequest;
import com.dylan.esquery.api.model.VectorSearchRequest;
import com.dylan.esquery.config.EsQueryProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.List;
import java.util.Map;

class EsDocumentServiceTest {

	private final ObjectMapper objectMapper = new ObjectMapper();
	private EsDocumentService service;

	@BeforeEach
	void setUp() {
		EsQueryProperties properties = new EsQueryProperties();
		properties.setTotalHitsThreshold(10000);
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
}
