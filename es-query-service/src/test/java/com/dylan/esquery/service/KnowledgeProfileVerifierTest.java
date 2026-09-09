package com.dylan.esquery.service;

import static com.dylan.esquery.KnowledgeTestProfiles.enabledProperties;
import static com.dylan.esquery.KnowledgeTestProfiles.defaultSourceFields;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.nio.charset.StandardCharsets;

import org.apache.http.entity.ContentType;
import org.apache.http.nio.entity.NStringEntity;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.RestClient;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.ArgumentCaptor;

import com.dylan.esquery.config.KnowledgeSearchProperties;
import com.dylan.esquery.config.KnowledgeSearchProperties.KnowledgeSearchProfile;
import com.fasterxml.jackson.databind.ObjectMapper;

class KnowledgeProfileVerifierTest {

	@Test
	void verifiesAliasUuidMappingAndCanonicalSnapshot() throws Exception {
		String snapshot = KnowledgeProfileVerifier.snapshot("tax-policy-v1",
				"agent-doc-tax-policy-v2-000001", "index-uuid-1",
				"tax-knowledge-search-v1", "mapping-v1");
		KnowledgeSearchProperties properties = enabledProperties(snapshot);
		RestClient client = mock(RestClient.class);
		Response aliasResponse = response(aliasJson(false));
		Response settingsResponse = response(settingsJson("index-uuid-1"));
		Response mappingResponse = response(mappingJson());
		when(client.performRequest(any())).thenReturn(aliasResponse, settingsResponse, mappingResponse);

		new KnowledgeProfileVerifier(client, new ObjectMapper(), properties)
				.verify("tax-policy-v1", properties.requireProfile("tax.policy", "tax-policy-v1"));
		ArgumentCaptor<Request> requests = ArgumentCaptor.forClass(Request.class);
		verify(client, times(3)).performRequest(requests.capture());
		assertThat(requests.getAllValues()).allSatisfy(request ->
				org.assertj.core.api.Assertions.assertThat(request.getOptions().getHeaders())
						.anySatisfy(header -> {
							org.assertj.core.api.Assertions.assertThat(header.getName())
									.isEqualToIgnoringCase("Accept-Encoding");
							org.assertj.core.api.Assertions.assertThat(header.getValue()).isEqualTo("identity");
						}));
	}

	@Test
	void rejectsWriteAliasAndSnapshotDrift() throws Exception {
		KnowledgeSearchProperties properties = enabledProperties("0".repeat(64));
		KnowledgeSearchProfile profile = properties.requireProfile("tax.policy", "tax-policy-v1");
		RestClient client = mock(RestClient.class);
		Response aliasResponse = response(aliasJson(true));
		when(client.performRequest(any())).thenReturn(aliasResponse);

		assertThatThrownBy(() -> new KnowledgeProfileVerifier(client, new ObjectMapper(), properties)
				.verify("tax-policy-v1", profile)).isInstanceOf(IllegalStateException.class);
	}

	@Test
	void rejectsCompressedTrailingAndIncompatibleMetadata() throws Exception {
		KnowledgeSearchProperties properties = enabledProperties("0".repeat(64));
		KnowledgeSearchProfile profile = properties.requireProfile("tax.policy", "tax-policy-v1");

		RestClient compressedClient = mock(RestClient.class);
		Response compressedResponse = response(aliasJson(false), "application/json", "gzip");
		when(compressedClient.performRequest(any())).thenReturn(compressedResponse);
		assertThatThrownBy(() -> new KnowledgeProfileVerifier(compressedClient,
				new ObjectMapper(), properties).verify("tax-policy-v1", profile))
				.isInstanceOf(IllegalStateException.class);

		RestClient trailingClient = mock(RestClient.class);
		Response trailingResponse = response(aliasJson(false) + " {}", "application/json", null);
		when(trailingClient.performRequest(any())).thenReturn(trailingResponse);
		assertThatThrownBy(() -> new KnowledgeProfileVerifier(trailingClient,
				new ObjectMapper(), properties).verify("tax-policy-v1", profile))
				.isInstanceOf(IllegalStateException.class);

		RestClient incompatibleClient = mock(RestClient.class);
		Response aliasResponse = response(aliasJson(false));
		Response settingsResponse = response(settingsJson("index-uuid-1"));
		Response incompatibleMappingResponse = response(mappingJson().replace(
				"\"content\":{\"type\":\"text\"}", "\"content\":{\"type\":\"long\"}"));
		when(incompatibleClient.performRequest(any())).thenReturn(
				aliasResponse, settingsResponse, incompatibleMappingResponse);
		assertThatThrownBy(() -> new KnowledgeProfileVerifier(incompatibleClient,
				new ObjectMapper(), properties).verify("tax-policy-v1", profile))
				.isInstanceOf(IllegalStateException.class);
	}

	private static Response response(String json) throws Exception {
		return response(json, "application/json", null);
	}

	@ParameterizedTest
	@ValueSource(strings = {"{\"type\":\"keyword\"}", "{\"type\":\"constant_keyword\"}",
			"{\"type\":\"keyword\",\"index\":true}", "{\"type\":\"text\"}",
			"{\"type\":\"keyword\",\"index\":false}", "{\"type\":\"keyword\",\"normalizer\":\"lowercase\"}"})
	void validatesOnlyEnabledDocumentNumberMappings(String definition) throws Exception {
		String snapshot = KnowledgeProfileVerifier.snapshot("tax-policy-v1", "agent-doc-tax-policy-v2-000001",
				"index-uuid-1", "tax-knowledge-search-v1", "mapping-v1");
		String mapping = mappingJson().replace("\"document_number\":{\"type\":\"keyword\"}", "\"document_number\":" + definition);
		for (boolean flag : new boolean[] {false, true}) {
			KnowledgeSearchProperties properties = enabledProperties(snapshot, defaultSourceFields(), flag);
			RestClient client = mock(RestClient.class);
			Response alias = response(aliasJson(false));
			Response settings = response(settingsJson("index-uuid-1"));
			Response fields = response(mapping);
			when(client.performRequest(any())).thenReturn(alias, settings, fields);
			KnowledgeProfileVerifier verifier = new KnowledgeProfileVerifier(client, new ObjectMapper(), properties);
			boolean invalid = definition.contains("text") || definition.contains("false") || definition.contains("normalizer");
			if (flag && invalid) {
				assertThatThrownBy(() -> verifier.verify("tax-policy-v1", properties.requireProfile("tax.policy", "tax-policy-v1")))
						.isInstanceOf(IllegalStateException.class);
			} else {
				verifier.verify("tax-policy-v1", properties.requireProfile("tax.policy", "tax-policy-v1"));
			}
			verify(client, times(3)).performRequest(any());
		}
	}

	private static Response response(String json, String contentType, String contentEncoding) throws Exception {
		Response response = mock(Response.class);
		when(response.getEntity()).thenReturn(new NStringEntity(json, ContentType.APPLICATION_JSON));
		when(response.getHeader("Content-Type")).thenReturn(contentType);
		when(response.getHeader("Content-Encoding")).thenReturn(contentEncoding);
		return response;
	}

	private static String aliasJson(boolean write) {
		return "{\"agent-doc-tax-policy-v2-000001\":{\"aliases\":{\"agent-doc-tax-policy-v2-read\":{\"is_write_index\":"
				+ write + "}}}}";
	}

	private static String settingsJson(String uuid) {
		return "{\"agent-doc-tax-policy-v2-000001\":{\"settings\":{\"index\":{\"uuid\":\"" + uuid + "\"}}}}";
	}

	private static String mappingJson() {
		String scalar = "{\"type\":\"keyword\"}";
		return "{\"agent-doc-tax-policy-v2-000001\":{\"mappings\":{\"_meta\":{\"mapping_version\":\"mapping-v1\"},\"properties\":{"
				+ "\"category\":" + scalar + ",\"title\":{\"type\":\"text\"},\"content\":{\"type\":\"text\"},"
				+ "\"embedding\":{\"type\":\"dense_vector\",\"dims\":1024},"
				+ "\"document_id\":" + scalar + ",\"chunk_id\":" + scalar + ",\"source_url\":" + scalar + ","
				+ "\"document_number\":" + scalar + ",\"written_date\":{\"type\":\"date\"},"
				+ "\"material_type\":" + scalar + ",\"policy_ref\":" + scalar + "}}}}";
	}
}
