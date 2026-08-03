package com.dylan.esquery.service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestClient;
import org.springframework.beans.factory.SmartInitializingSingleton;

import com.dylan.esquery.config.KnowledgeSearchProperties;
import com.dylan.esquery.config.KnowledgeSearchProperties.KnowledgeSearchProfile;
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
		this.objectMapper = objectMapper;
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
			if (definition == null || definition.isMissingNode()) {
				throw invalid(profileId);
			}
		}
		JsonNode vector = fieldDefinition(propertiesNode, profile.getVectorField());
		if (!"dense_vector".equals(vector.path("type").asText()) || vector.path("dims").asInt(-1) != 1024) {
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
		Response response = restClient.performRequest(new Request("GET", endpoint));
		byte[] body = response.getEntity().getContent().readNBytes(MAX_METADATA_BYTES + 1);
		if (body.length == 0 || body.length > MAX_METADATA_BYTES) {
			throw new IOException("Knowledge metadata response size is invalid");
		}
		return objectMapper.readTree(body);
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
