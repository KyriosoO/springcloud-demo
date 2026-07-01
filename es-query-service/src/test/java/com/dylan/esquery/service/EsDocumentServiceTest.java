package com.dylan.esquery.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import com.dylan.esquery.config.EsQueryProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

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
}
