package com.dylan.esquery.service;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

import org.apache.http.HttpHeaders;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestClient;
import org.elasticsearch.client.RequestOptions;
import org.springframework.beans.factory.SmartInitializingSingleton;

import com.dylan.esquery.config.KnowledgeSearchProperties;
import com.dylan.esquery.config.KnowledgeSearchProperties.KnowledgeSearchProfile;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/** Performs the enabled-profile alias, UUID, mapping and snapshot startup check. */
public final class KnowledgeProfileVerifier implements SmartInitializingSingleton {
	private static final int MAX_METADATA_BYTES = 2 * 1024 * 1024;
	private final RestClient restClient;
	private final ObjectMapper objectMapper;
	private final KnowledgeSearchProperties properties;

	public KnowledgeProfileVerifier(RestClient restClient, ObjectMapper objectMapper,
			KnowledgeSearchProperties properties) {
		this.restClient = restClient;
		this.objectMapper = objectMapper.copy()
				.enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION)
				.enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);
		this.properties = properties;
	}

	@Override
	public void afterSingletonsInstantiated() {
		for (Map.Entry<String, KnowledgeSearchProfile> entry : properties.getProfiles().entrySet()) {
			verify(entry.getKey(), entry.getValue());
		}
	}

	void verify(String profileId, KnowledgeSearchProfile profile) {
		try {
			JsonNode aliasRoot = getJson("/_alias/" + profile.getReadAlias());
			if (aliasRoot.size() != 1 || !aliasRoot.has(profile.getExpectedIndexName())) {
				throw invalid(profileId);
			}
			JsonNode alias = aliasRoot.path(profile.getExpectedIndexName())
					.path("aliases").path(profile.getReadAlias());
			if (!alias.isObject() || alias.path("is_write_index").asBoolean(false)) {
				throw invalid(profileId);
			}

			JsonNode settings = getJson("/" + profile.getExpectedIndexName() + "/_settings");
			String uuid = settings.path(profile.getExpectedIndexName()).path("settings")
					.path("index").path("uuid").asText(null);
			if (!profile.getExpectedIndexUuid().equals(uuid)) {
				throw invalid(profileId);
			}

			JsonNode mapping = getJson("/" + profile.getExpectedIndexName() + "/_mapping")
					.path(profile.getExpectedIndexName()).path("mappings");
			if (!profile.getMappingVersion().equals(mapping.path("_meta").path("mapping_version").asText(null))) {
				throw invalid(profileId);
			}
			verifyFields(profileId, profile, mapping.path("properties"));
			String expectedSnapshot = snapshot(profileId, profile.getExpectedIndexName(), uuid,
					profile.getProfileVersion(), profile.getMappingVersion());
			if (!profile.getIndexSnapshotId().equals(expectedSnapshot)) {
				throw invalid(profileId);
			}
		} catch (IOException ex) {
			throw new IllegalStateException("Knowledge profile verification failed: " + profileId, ex);
		}
	}

	private void verifyFields(String profileId, KnowledgeSearchProfile profile, JsonNode propertiesNode) {
		Set<String> fields = new LinkedHashSet<>();
		fields.add(profile.getCategoryField());
		fields.addAll(profile.getKeywordFields());
		fields.addAll(profile.getSourceFields().values());
		fields.add(profile.getVectorField());
		for (String field : fields) {
			JsonNode definition = fieldDefinition(propertiesNode, field);
			if (definition == null || definition.isMissingNode()
					|| definition.path("type").asText("").isBlank()) {
				throw invalid(profileId);
			}
		}
		requireType(profileId, propertiesNode, profile.getCategoryField(),
				Set.of("keyword", "constant_keyword"));
		for (String field : profile.getKeywordFields()) {
			requireType(profileId, propertiesNode, field,
					Set.of("text", "match_only_text", "keyword"));
		}
		for (Map.Entry<String, String> sourceField : profile.getSourceFields().entrySet()) {
			Set<String> allowedTypes = "written-date".equals(sourceField.getKey())
					? Set.of("date")
					: Set.of("text", "match_only_text", "keyword", "constant_keyword", "wildcard");
			requireType(profileId, propertiesNode, sourceField.getValue(), allowedTypes);
		}
		JsonNode vector = fieldDefinition(propertiesNode, profile.getVectorField());
		if (!"dense_vector".equals(vector.path("type").asText()) || vector.path("dims").asInt(-1) != 1024) {
			throw invalid(profileId);
		}
	}

	private static void requireType(String profileId, JsonNode propertiesNode,
			String field, Set<String> allowedTypes) {
		String type = fieldDefinition(propertiesNode, field).path("type").asText("");
		if (!allowedTypes.contains(type)) {
			throw invalid(profileId);
		}
	}

	private static JsonNode fieldDefinition(JsonNode propertiesNode, String dottedField) {
		JsonNode currentProperties = propertiesNode;
		JsonNode definition = null;
		String[] parts = dottedField.split("\\.");
		for (int index = 0; index < parts.length; index++) {
			definition = currentProperties.path(parts[index]);
			if (definition.isMissingNode()) {
				return definition;
			}
			if (index + 1 < parts.length) {
				currentProperties = definition.path("properties");
			}
		}
		return definition;
	}

	private JsonNode getJson(String endpoint) throws IOException {
		Request request = new Request("GET", endpoint);
		request.setOptions(RequestOptions.DEFAULT.toBuilder()
				.addHeader(HttpHeaders.ACCEPT_ENCODING, "identity"));
		Response response = restClient.performRequest(request);
		if (response == null || response.getEntity() == null) {
			throw new IOException("Knowledge metadata response is empty");
		}
		String contentType = response.getHeader("Content-Type");
		String contentEncoding = response.getHeader("Content-Encoding");
		if (contentType == null || !contentType.toLowerCase().startsWith("application/json")
				|| contentEncoding != null && !"identity".equalsIgnoreCase(contentEncoding)) {
			throw new IOException("Knowledge metadata response media type is invalid");
		}
		try (InputStream input = response.getEntity().getContent()) {
			byte[] body = input.readNBytes(MAX_METADATA_BYTES + 1);
			if (body.length == 0 || body.length > MAX_METADATA_BYTES) {
				throw new IOException("Knowledge metadata response size is invalid");
			}
			return objectMapper.readTree(body);
		}
	}

	static String snapshot(String profileId, String indexName, String indexUuid,
			String profileVersion, String mappingVersion) {
		String canonical = String.join("\n", profileId, indexName, indexUuid, profileVersion, mappingVersion);
		try {
			return java.util.HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
					.digest(canonical.getBytes(StandardCharsets.UTF_8)));
		} catch (Exception ex) {
			throw new IllegalStateException(ex);
		}
	}

	private static IllegalStateException invalid(String profileId) {
		return new IllegalStateException("Knowledge profile verification failed: " + profileId);
	}
}
