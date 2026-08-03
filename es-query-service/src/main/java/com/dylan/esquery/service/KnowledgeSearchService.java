package com.dylan.esquery.service;

import java.io.IOException;
import java.io.InputStream;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.text.Normalizer;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.apache.http.entity.ContentType;
import org.apache.http.HttpHeaders;
import org.apache.http.nio.entity.NStringEntity;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.ResponseException;
import org.elasticsearch.client.RestClient;
import org.elasticsearch.client.RequestOptions;

import com.dylan.esquery.api.knowledge.KnowledgeSearchCandidate;
import com.dylan.esquery.api.knowledge.KnowledgeSearchRequest;
import com.dylan.esquery.api.knowledge.KnowledgeSearchResponse;
import com.dylan.esquery.config.KnowledgeSearchProperties;
import com.dylan.esquery.config.KnowledgeSearchProperties.KnowledgeSearchProfile;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeAuthorityUnavailableException;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeProviderException;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeRateLimitedException;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeTimeoutException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;

public final class KnowledgeSearchService {
	private static final int MAX_ES_RESPONSE_BYTES = 2 * 1024 * 1024;

	private final RestClient restClient;
	private final ObjectMapper objectMapper;
	private final KnowledgeSearchProperties properties;

	public KnowledgeSearchService(RestClient restClient, ObjectMapper objectMapper,
			KnowledgeSearchProperties properties) {
		this.restClient = restClient;
		this.objectMapper = objectMapper.copy()
				.enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION)
				.enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);
		this.properties = properties;
	}

	public KnowledgeSearchResponse search(KnowledgeSearchRequest request, KnowledgeReadDecision decision) {
		if (decision == null || !request.logicalDomainId().equals(decision.logicalDomainId())
				|| !request.retrievalProfileId().equals(decision.retrievalProfileId())) {
			throw new KnowledgeAuthorityUnavailableException();
		}
		KnowledgeSearchProfile profile = properties.requireProfile(
				request.logicalDomainId(), request.retrievalProfileId());
		if (!profile.getProfileVersion().equals(decision.profileVersion())
				|| !profile.getReadPolicyVersion().equals(decision.readPolicyVersion())) {
			throw new KnowledgeAuthorityUnavailableException();
		}

		Request esRequest = new Request("POST", "/" + profile.getReadAlias() + "/_search");
		esRequest.setOptions(RequestOptions.DEFAULT.toBuilder()
				.addHeader(HttpHeaders.ACCEPT_ENCODING, "identity"));
		try {
			esRequest.setEntity(new NStringEntity(
					objectMapper.writeValueAsString(buildSearchBody(request, profile)),
					ContentType.APPLICATION_JSON));
			Response response = restClient.performRequest(esRequest);
			byte[] responseBody = readJsonResponse(response);
			return decodeSearchResponse(responseBody, request, profile);
		} catch (ResponseException ex) {
			if (ex.getResponse().getStatusLine().getStatusCode() == 429) {
				throw new KnowledgeRateLimitedException();
			}
			throw new KnowledgeProviderException(ex);
		} catch (SocketTimeoutException ex) {
			throw new KnowledgeTimeoutException(ex);
		} catch (IOException ex) {
			if (hasSocketTimeout(ex)) {
				throw new KnowledgeTimeoutException(ex);
			}
			throw new KnowledgeProviderException(ex);
		}
	}

	Map<String, Object> buildSearchBody(KnowledgeSearchRequest request, KnowledgeSearchProfile profile) {
		Map<String, Object> categoryFilter = Map.of("terms",
				Map.of(profile.getCategoryField(), profile.getCategoryValues()));
		Map<String, Object> body = new LinkedHashMap<>();
		body.put("_source", Map.of("includes", new ArrayList<>(
				new LinkedHashSet<>(profile.getSourceFields().values()))));
		body.put("track_total_hits", false);
		if ("keyword".equals(request.path())) {
			body.put("size", request.limit() + 1);
			body.put("query", Map.of("bool", Map.of(
					"filter", List.of(categoryFilter),
					"must", List.of(Map.of("multi_match", Map.of(
							"query", request.queryText(), "fields", profile.getKeywordFields()))))));
		} else {
			Map<String, Object> knn = new LinkedHashMap<>();
			knn.put("field", profile.getVectorField());
			knn.put("query_vector", request.queryVector());
			knn.put("k", request.limit() + 1);
			knn.put("num_candidates", Math.min(100, Math.max(20, 5 * (request.limit() + 1))));
			knn.put("filter", categoryFilter);
			body.put("knn", knn);
		}
		return body;
	}

	KnowledgeSearchResponse decodeSearchResponse(byte[] body, KnowledgeSearchRequest request,
			KnowledgeSearchProfile profile) {
		try {
			JsonNode hits = objectMapper.readTree(body).path("hits").path("hits");
			if (!hits.isArray() || hits.size() > request.limit() + 1) {
				throw new KnowledgeProviderException();
			}
			List<ScoredCandidate> validated = new ArrayList<>();
			Set<String> identities = new HashSet<>();
			for (JsonNode hit : hits) {
				double score = requiredFiniteScore(hit.get("_score"));
				JsonNode source = hit.get("_source");
				if (source == null || !source.isObject()) {
					throw new KnowledgeProviderException();
				}
				KnowledgeSearchCandidate candidate = mapCandidate(source, request, profile, 0);
				String identity = candidate.documentId() + "\n" + candidate.chunkId();
				if (!identities.add(identity)) {
					throw new KnowledgeProviderException();
				}
				validated.add(new ScoredCandidate(score, candidate));
			}
			validated.sort(Comparator.comparingDouble(ScoredCandidate::score).reversed()
					.thenComparing(item -> item.candidate().chunkId()));
			boolean truncated = validated.size() > request.limit();
			List<KnowledgeSearchCandidate> candidates = new ArrayList<>();
			for (int index = 0; index < Math.min(request.limit(), validated.size()); index++) {
				KnowledgeSearchCandidate source = validated.get(index).candidate();
				candidates.add(new KnowledgeSearchCandidate(source.documentId(), source.chunkId(),
						source.logicalDomainId(), source.title(), source.content(), source.sourceUrl(),
						source.documentNumber(), source.writtenDate(), source.materialType(), index + 1,
						source.contentSha256(), source.policyRef()));
			}
			return new KnowledgeSearchResponse(1, request.logicalDomainId(), request.retrievalProfileId(),
					request.path(), profile.getProfileVersion(), profile.getIndexSnapshotId(),
					profile.getReadPolicyVersion(), truncated, candidates);
		} catch (KnowledgeProviderException ex) {
			throw ex;
		} catch (Exception ex) {
			throw new KnowledgeProviderException(ex);
		}
	}

	private static KnowledgeSearchCandidate mapCandidate(JsonNode source, KnowledgeSearchRequest request,
			KnowledgeSearchProfile profile, int rank) {
		Map<String, String> fields = profile.getSourceFields();
		Set<String> allowedFields = Set.copyOf(fields.values());
		validateSourceFields(source, "", allowedFields);
		String documentId = requiredNfcText(source, fields.get("document-id"), 256, false);
		String chunkId = requiredNfcText(source, fields.get("chunk-id"), 256, false);
		String title = requiredNfcText(source, fields.get("title"), 256, true);
		String content = requiredNfcText(source, fields.get("content"), profile.getMaxContentChars(), false);
		String sourceUrl = optionalNfcText(source, fields.get("source-url"), 1024);
		String documentNumber = optionalNfcText(source, fields.get("document-number"), 256);
		LocalDate writtenDate = optionalDate(source, fields.get("written-date"));
		String materialType = requiredNfcText(source, fields.get("material-type"), 256, false);
		String policyRef = requiredNfcText(source, fields.get("policy-ref"), 256, false);
		return new KnowledgeSearchCandidate(documentId, chunkId, request.logicalDomainId(), title, content,
				sourceUrl, documentNumber, writtenDate, materialType, rank, sha256(content), policyRef);
	}

	private static double requiredFiniteScore(JsonNode node) {
		if (node == null || !node.isNumber() || !Double.isFinite(node.doubleValue())) {
			throw new KnowledgeProviderException();
		}
		return node.doubleValue();
	}

	private static String requiredNfcText(JsonNode source, String field, int maxCodePoints, boolean emptyAllowed) {
		JsonNode node = sourceAt(source, field);
		if (node == null || !node.isTextual()) {
			throw new KnowledgeProviderException();
		}
		String value = node.textValue();
		if ((!emptyAllowed && value.isBlank()) || !value.equals(Normalizer.normalize(value, Normalizer.Form.NFC))
				|| value.codePointCount(0, value.length()) > maxCodePoints) {
			throw new KnowledgeProviderException();
		}
		return value;
	}

	private static String optionalNfcText(JsonNode source, String field, int maxCodePoints) {
		JsonNode node = sourceAt(source, field);
		if (node == null || node.isNull()) {
			return null;
		}
		return requiredNfcText(source, field, maxCodePoints, true);
	}

	private static LocalDate optionalDate(JsonNode source, String field) {
		JsonNode node = sourceAt(source, field);
		if (node == null || node.isNull()) {
			return null;
		}
		if (!node.isTextual()) {
			throw new KnowledgeProviderException();
		}
		try {
			return LocalDate.parse(node.textValue());
		} catch (DateTimeParseException ex) {
			throw new KnowledgeProviderException(ex);
		}
	}

	private static byte[] readJsonResponse(Response response) throws IOException {
		if (response == null || response.getEntity() == null) {
			throw new KnowledgeProviderException();
		}
		String contentType = response.getHeader("Content-Type");
		String contentEncoding = response.getHeader("Content-Encoding");
		if (contentType == null || !contentType.toLowerCase().startsWith("application/json")
				|| (contentEncoding != null && !"identity".equalsIgnoreCase(contentEncoding))) {
			throw new KnowledgeProviderException();
		}
		try (InputStream input = response.getEntity().getContent()) {
			byte[] body = input.readNBytes(MAX_ES_RESPONSE_BYTES + 1);
			if (body.length == 0 || body.length > MAX_ES_RESPONSE_BYTES) {
				throw new KnowledgeProviderException();
			}
			return body;
		}
	}

	private static JsonNode sourceAt(JsonNode source, String dottedField) {
		JsonNode current = source;
		for (String part : dottedField.split("\\.")) {
			if (current == null || !current.isObject()) {
				return null;
			}
			current = current.get(part);
		}
		return current;
	}

	private static void validateSourceFields(JsonNode node, String prefix, Set<String> allowedFields) {
		if (!node.isObject()) {
			if (!allowedFields.contains(prefix)) {
				throw new KnowledgeProviderException();
			}
			return;
		}
		node.properties().forEach(entry -> {
			String path = prefix.isEmpty() ? entry.getKey() : prefix + "." + entry.getKey();
			validateSourceFields(entry.getValue(), path, allowedFields);
		});
	}

	private static boolean hasSocketTimeout(Throwable throwable) {
		for (Throwable current = throwable; current != null; current = current.getCause()) {
			if (current instanceof SocketTimeoutException) {
				return true;
			}
		}
		return false;
	}

	private static String sha256(String value) {
		try {
			byte[] digest = MessageDigest.getInstance("SHA-256")
					.digest(Normalizer.normalize(value, Normalizer.Form.NFC)
							.getBytes(StandardCharsets.UTF_8));
			return java.util.HexFormat.of().formatHex(digest);
		} catch (Exception ex) {
			throw new IllegalStateException(ex);
		}
	}

	private record ScoredCandidate(double score, KnowledgeSearchCandidate candidate) {
	}
}
