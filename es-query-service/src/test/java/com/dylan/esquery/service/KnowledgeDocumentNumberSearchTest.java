package com.dylan.esquery.service;

import static com.dylan.esquery.KnowledgeTestProfiles.defaultSourceFields;
import static com.dylan.esquery.KnowledgeTestProfiles.enabledProperties;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import org.apache.http.HttpHost;
import org.elasticsearch.client.RestClient;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import com.dylan.esquery.api.knowledge.KnowledgeSearchRequest;
import com.dylan.esquery.config.KnowledgeSearchProperties;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeAuthorityUnavailableException;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeProviderException;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeTimeoutException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;

class KnowledgeDocumentNumberSearchTest {
	private final ObjectMapper mapper = new ObjectMapper();
	private final KnowledgeSearchProperties enabled = enabledProperties("0".repeat(64), defaultSourceFields(), true);

	@Test
	void defaultDisabledNoReferenceAndVectorKeepOriginalQueries() {
		KnowledgeSearchProperties disabled = enabledProperties("0".repeat(64));
		assertThat(disabled.requireProfile("tax.policy", "tax-policy-v1").isDocumentNumberMatching()).isFalse();
		assertThat(body(disabled, request("甲乙〔2031〕1号")).toString()).doesNotContain("regexp", "constant_score");
		assertThat(body(enabled, request("普通政策问题"))).isEqualTo(body(disabled, request("普通政策问题")));
		KnowledgeSearchRequest vector = new KnowledgeSearchRequest(1, "tax.policy", "tax-policy-v1", "vector",
				null, Collections.nCopies(1024, 0.25), 20);
		assertThat(body(enabled, vector)).isEqualTo(body(disabled, vector));
	}

	@ParameterizedTest
	@ValueSource(strings = {"请查询甲乙公告2031年第1号和2032年第2号的区别",
			"甲乙公告2031年第1号 甲乙公告2032年第2号 执行期限",
			"甲乙公告2031年第1号　甲乙公告2032年第2号 执行期限"})
	void optionalSignalUsesFixedMappingAndPreservesTextFilterAndBounds(String text) {
		Map<String, String> fields = new LinkedHashMap<>(defaultSourceFields());
		fields.put("document-number", "metadata.officialNumber");
		KnowledgeSearchProperties properties = enabledProperties("0".repeat(64), fields, true);
		JsonNode result = body(properties, request(text));
		JsonNode query = result.path("query").path("bool");
		assertThat(result.path("size").asInt()).isEqualTo(21);
		assertThat(result.path("track_total_hits").asBoolean()).isFalse();
		assertThat(query.path("filter").get(0).path("terms").path("category").get(0).asText()).isEqualTo("policy");
		assertThat(query.path("minimum_should_match").asInt()).isEqualTo(1);
		assertThat(query.path("should").get(0).path("multi_match").path("query").asText()).isEqualTo(text);
		JsonNode metadata = query.path("should").get(1).path("constant_score");
		assertThat(metadata.path("boost").asInt()).isEqualTo(100);
		assertThat(metadata.path("filter").path("bool").path("minimum_should_match").asInt()).isEqualTo(1);
		JsonNode clauses = metadata.path("filter").path("bool").path("should");
		assertThat(clauses.size()).isEqualTo(2);
		assertThat("甲乙公告2031年第1号").matches(clauses.get(0).path("regexp")
				.path("metadata.officialNumber").path("value").asText());
		assertThat("甲乙公告2032年第2号").matches(clauses.get(1).path("regexp")
				.path("metadata.officialNumber").path("value").asText());
		for (JsonNode clause : clauses) {
			JsonNode regex = clause.path("regexp").path("metadata.officialNumber");
			assertThat(regex.path("flags").asText()).isEqualTo("NONE");
			assertThat(regex.path("case_insensitive").asBoolean()).isFalse();
			assertThat(regex.path("max_determinized_states").asInt()).isEqualTo(256);
			assertThat(regex.path("value").asText()).hasSizeLessThanOrEqualTo(900).doesNotContain(".*");
		}
	}

	@Test
	void missingOrStaleReadDecisionMakesZeroRequests() {
		RestClient client = mock(RestClient.class);
		KnowledgeSearchService service = new KnowledgeSearchService(client, mapper, enabled);
		assertThatThrownBy(() -> service.search(request("甲乙〔2031〕1号"), null))
				.isInstanceOf(KnowledgeAuthorityUnavailableException.class);
		for (KnowledgeReadDecision invalid : List.of(
				new KnowledgeReadDecision("tax.law", "tax-policy-v1", "tax-knowledge-search-v1", "tax-public-authenticated-v1", "synthetic"),
				new KnowledgeReadDecision("tax.policy", "tax-policy-v1", "old", "tax-public-authenticated-v1", "synthetic"),
				new KnowledgeReadDecision("tax.policy", "tax-policy-v1", "tax-knowledge-search-v1", "old", "synthetic"))) {
			assertThatThrownBy(() -> service.search(request("甲乙〔2031〕1号"), invalid))
					.isInstanceOf(KnowledgeAuthorityUnavailableException.class);
		}
		verifyNoInteractions(client);
	}

	@Test
	void transportFailureAndTimeoutAreNotRetriedWithoutTheSignal() throws Exception {
		for (IOException failure : List.of(new SocketTimeoutException("synthetic"), new IOException("synthetic"))) {
			RestClient client = mock(RestClient.class);
			when(client.performRequest(any())).thenThrow(failure);
			KnowledgeSearchService service = new KnowledgeSearchService(client, mapper, enabled);
			KnowledgeReadDecision decision = new KnowledgeReadDecision("tax.policy", "tax-policy-v1",
					"tax-knowledge-search-v1", "tax-public-authenticated-v1", "synthetic");
			assertThatThrownBy(() -> service.search(request("甲乙〔2031〕1号"), decision))
					.isInstanceOf(failure instanceof SocketTimeoutException ? KnowledgeTimeoutException.class : KnowledgeProviderException.class);
			verify(client, times(1)).performRequest(any());
		}
	}

	@ParameterizedTest
	@ValueSource(ints = {200, 400})
	void sendsOneRealHttpRequestAndDoesNotRetryRejectedMetadataQuery(int status) throws Exception {
		AtomicInteger calls = new AtomicInteger();
		AtomicReference<String> method = new AtomicReference<>();
		AtomicReference<JsonNode> captured = new AtomicReference<>();
		HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
		server.createContext("/agent-doc-tax-policy-v2-read/_search", exchange -> {
			calls.incrementAndGet();
			method.set(exchange.getRequestMethod());
			captured.set(mapper.readTree(exchange.getRequestBody()));
			byte[] response = (status == 200 ? "{\"hits\":{\"hits\":[]}}" : "{\"error\":\"expensive_queries_disabled\",\"status\":400}")
					.getBytes(StandardCharsets.UTF_8);
			exchange.getResponseHeaders().add("Content-Type", "application/json");
			exchange.sendResponseHeaders(status, response.length);
			try (var output = exchange.getResponseBody()) { output.write(response); }
			exchange.close();
		});
		server.start();
		try (RestClient client = RestClient.builder(new HttpHost("127.0.0.1", server.getAddress().getPort())).build()) {
			KnowledgeSearchService service = new KnowledgeSearchService(client, mapper, enabled);
			KnowledgeReadDecision decision = new KnowledgeReadDecision("tax.policy", "tax-policy-v1",
					"tax-knowledge-search-v1", "tax-public-authenticated-v1", "synthetic");
			if (status == 200) {
				assertThat(service.search(request("甲乙〔2031〕1号"), decision).candidates()).isEmpty();
			} else {
				assertThatThrownBy(() -> service.search(request("甲乙〔2031〕1号"), decision))
						.isInstanceOf(KnowledgeProviderException.class);
			}
			assertThat(calls.get()).isEqualTo(1);
			assertThat(method.get()).isEqualTo("POST");
			assertThat(captured.get()).isEqualTo(body(enabled, request("甲乙〔2031〕1号")));
		} finally {
			server.stop(0);
		}
	}

	private JsonNode body(KnowledgeSearchProperties properties, KnowledgeSearchRequest request) {
		return mapper.valueToTree(new KnowledgeSearchService(null, mapper, properties)
				.buildSearchBody(request, properties.requireProfile("tax.policy", "tax-policy-v1")));
	}

	private static KnowledgeSearchRequest request(String query) {
		return new KnowledgeSearchRequest(1, "tax.policy", "tax-policy-v1", "keyword", query, null, 20);
	}
}
