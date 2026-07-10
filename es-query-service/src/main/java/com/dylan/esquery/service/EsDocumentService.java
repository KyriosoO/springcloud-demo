package com.dylan.esquery.service;

import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.apache.http.HttpEntity;
import org.apache.http.entity.ContentType;
import org.apache.http.nio.entity.NStringEntity;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.ResponseException;
import org.elasticsearch.client.RestClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import com.dylan.esquery.api.model.HybridContextWindow;
import com.dylan.esquery.api.model.HybridRetrievalDiagnostics;
import com.dylan.esquery.api.model.HybridSearchChannelRequest;
import com.dylan.esquery.api.model.HybridSearchHit;
import com.dylan.esquery.api.model.HybridSearchRequest;
import com.dylan.esquery.api.model.HybridSearchResponse;
import com.dylan.esquery.api.model.VectorSearchRequest;
import com.dylan.esquery.config.EsQueryProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

/**
 * ES 文档服务，封装 Elasticsearch 文档写入、删除和查询逻辑。
 */
@Service
public class EsDocumentService {
	private static final String DEFAULT_EMBEDDING_FIELD = "embedding";

	private final RestClient restClient;
	private final ObjectMapper objectMapper;
	private final EsQueryProperties properties;
	private final HybridSearchMerger hybridSearchMerger;
	private final DocumentIndexPolicy documentIndexPolicy;
	private final DocumentChunkSchemaValidator chunkSchemaValidator;
	private final DocumentIndexDefinitionValidator indexDefinitionValidator;

	/**
	 * 创建 EsDocumentService 实例并注入所需依赖。
	 */
	public EsDocumentService(RestClient restClient, ObjectMapper objectMapper, EsQueryProperties properties) {
		this(restClient, objectMapper, properties, new HybridSearchMerger(objectMapper),
				new DocumentIndexPolicy(properties), new DocumentChunkSchemaValidator(),
				new DocumentIndexDefinitionValidator());
	}

	/**
	 * 创建 EsDocumentService 实例并注入所需依赖。
	 */
	public EsDocumentService(
			RestClient restClient,
			ObjectMapper objectMapper,
			EsQueryProperties properties,
			HybridSearchMerger hybridSearchMerger) {
		this(restClient, objectMapper, properties, hybridSearchMerger,
				new DocumentIndexPolicy(properties), new DocumentChunkSchemaValidator(),
				new DocumentIndexDefinitionValidator());
	}

	public EsDocumentService(
			RestClient restClient,
			ObjectMapper objectMapper,
			EsQueryProperties properties,
			HybridSearchMerger hybridSearchMerger,
			DocumentIndexPolicy documentIndexPolicy,
			DocumentChunkSchemaValidator chunkSchemaValidator,
			DocumentIndexDefinitionValidator indexDefinitionValidator) {
		this.restClient = restClient;
		this.objectMapper = objectMapper;
		this.properties = properties;
		this.hybridSearchMerger = hybridSearchMerger;
		this.documentIndexPolicy = documentIndexPolicy;
		this.chunkSchemaValidator = chunkSchemaValidator;
		this.indexDefinitionValidator = indexDefinitionValidator;
	}

	@Autowired
	public EsDocumentService(
			RestClient restClient,
			ObjectMapper objectMapper,
			EsQueryProperties properties,
			DocumentIndexPolicy documentIndexPolicy,
			DocumentChunkSchemaValidator chunkSchemaValidator,
			DocumentIndexDefinitionValidator indexDefinitionValidator) {
		this(restClient, objectMapper, properties, new HybridSearchMerger(objectMapper),
				documentIndexPolicy, chunkSchemaValidator, indexDefinitionValidator);
	}

	/**
	 * 执行领域搜索。
	 */
	public String search(String index, String queryDsl) throws IOException {
		Request request = new Request("POST", "/" + index + "/_search");
		request.setEntity(jsonEntity(applyDefaultTrackTotalHits(queryDsl)));
		Response response = restClient.performRequest(request);
		return responseBody(response);
	}

	/**
	 * 处理 indexDocument 相关逻辑。
	 */
	public String indexDocument(String index, String id, Map<String, Object> document) throws IOException {
		validateDocumentChunkIfNeeded(index, document);
		String endpoint = id == null || id.isBlank() ? "/" + index + "/_doc" : "/" + index + "/_doc/" + id;
		Request request = new Request(id == null || id.isBlank() ? "POST" : "PUT", endpoint);
		request.setEntity(jsonEntity(objectMapper.writeValueAsString(document)));
		Response response = restClient.performRequest(request);
		return responseBody(response);
	}

	/**
	 * 删除业务数据。
	 */
	public String deleteDocument(String index, String id) throws IOException {
		if (id == null || id.isBlank()) {
			throw new IllegalArgumentException("document id must not be blank");
		}
		Request request = new Request("DELETE", "/" + index + "/_doc/" + id);
		Response response = restClient.performRequest(request);
		return responseBody(response);
	}

	/**
	 * 批量处理索引文档。
	 */
	public String bulkIndex(String index, String idField, List<Map<String, Object>> documents) throws IOException {
		if (documentIndexPolicy.isDocumentIndex(index) && (idField == null || idField.isBlank())) {
			throw new IllegalArgumentException("document index bulk idField must not be blank");
		}
		if (documents != null) {
			documents.forEach(document -> validateDocumentChunkIfNeeded(index, document));
		}
		String bulkBody = buildBulkBody(index, idField, documents);
		Request request = new Request("POST", "/_bulk");
		request.setEntity(new NStringEntity(bulkBody, ContentType.create("application/x-ndjson", "UTF-8")));
		Response response = restClient.performRequest(request);
		return responseBody(response);
	}

	/**
	 * 处理 recreateIndex 相关逻辑。
	 */
	public void recreateIndex(String index) throws IOException {
		recreateIndex(index, null);
	}
	
	/**
	 * 处理 recreateIndex 相关逻辑。
	 */
	public void recreateIndex(String index, Map<String, Object> indexDefinition) throws IOException {
		if (documentIndexPolicy.isDocumentIndex(index)) {
			indexDefinitionValidator.validate(index, indexDefinition);
		}
		deleteIndexIfExists(index);
		Request createRequest = new Request("PUT", "/" + index);
		if (indexDefinition != null && !indexDefinition.isEmpty()) {
	        createRequest.setEntity(jsonEntity(objectMapper.writeValueAsString(indexDefinition)));
	    }
		restClient.performRequest(createRequest);
	}

	/**
	 * 向量索引能力
	 * @param index
	 * @param request
	 * @return
	 * @throws IOException
	 */
	public String vectorSearch(String index, VectorSearchRequest request) throws IOException {
		Map<String, Object> body = vectorSearchBody(index, request);
		Request esRequest = new Request("POST", "/" + index + "/_search");
		esRequest.setEntity(jsonEntity(objectMapper.writeValueAsString(body)));
		Response response = restClient.performRequest(esRequest);
		return responseBody(response);
	}

	/**
	 * 执行关键词和向量双路召回后使用 RRF 融合。
	 */
	public HybridSearchResponse hybridSearch(String index, HybridSearchRequest request) throws IOException {
		validateHybridRequest(index, request);
		Map<String, List<JsonNode>> hitsByChannel = new LinkedHashMap<>();
		for (HybridSearchChannelRequest channel : request.getChannels()) {
			String channelName = normalizedChannel(channel.getChannel());
			Request esRequest = new Request("POST", "/" + index + "/_search");
			Map<String, Object> body = channelSearchBody(index, request, channel);
			esRequest.setEntity(jsonEntity(objectMapper.writeValueAsString(body)));
			Response esResponse = restClient.performRequest(esRequest);
			hitsByChannel.put(channelName, extractHits(objectMapper.readTree(responseBody(esResponse))));
		}
		List<HybridSearchHit> hits = hybridSearchMerger.merge(hitsByChannel, request);
		enrichContextWindow(index, request, hits);
		HybridRetrievalDiagnostics diagnostics = new HybridRetrievalDiagnostics();
		Map<String, Integer> channelHitCounts = channelHitCounts(hitsByChannel);
		diagnostics.setChannelHitCounts(channelHitCounts);
		diagnostics.setKeywordHitCount(keywordCount(channelHitCounts));
		diagnostics.setVectorHitCount(vectorCount(channelHitCounts));
		diagnostics.setReturnedHitCount(hits.size());
		diagnostics.setFusedCandidateCount(hitsByChannel.values().stream().mapToInt(List::size).sum());
		diagnostics.setDedupedCandidateCount(hits.size());
		diagnostics.setRrfK(HybridSearchMerger.positiveOrDefault(request.getRrfK(), 60, "rrfK"));
		diagnostics.setMaxChunksPerDocument(HybridSearchMerger.positiveOrDefault(
				request.getMaxChunksPerDocument(), 1, "maxChunksPerDocument"));
		diagnostics.setFusionStrategy("RRF");
		diagnostics.setChannelWeights(request.getChannelWeights());
		diagnostics.setPermissionEvidenceId(request.getPermissionEvidenceId());
		diagnostics.setPermissionVersion(request.getPermissionVersion());
		diagnostics.setFilterDigest(request.getFilterDigest());
		diagnostics.setRerankStatus("NOT_REQUESTED");
		diagnostics.setDegraded(false);
		HybridSearchResponse response = new HybridSearchResponse();
		response.setHits(hits);
		response.setDiagnostics(diagnostics);
		response.setPartial(false);
		return response;
	}

	private Map<String, Object> channelSearchBody(
			String index,
			HybridSearchRequest request,
			HybridSearchChannelRequest channel) {
		String channelName = normalizedChannel(channel.getChannel());
		if ("DENSE_VECTOR".equals(channelName)) {
			VectorSearchRequest vectorRequest = new VectorSearchRequest();
			vectorRequest.setEmbeddingField(channel.getEmbeddingField() == null ? request.getEmbeddingField() : channel.getEmbeddingField());
			vectorRequest.setQueryVector(channel.getQueryVector() == null ? request.getQueryVector() : channel.getQueryVector());
			vectorRequest.setFilterDsl(request.getFilters());
			vectorRequest.setK(HybridSearchMerger.positiveOrDefault(
					channel.getK() == null ? request.getVectorK() : channel.getK(), 20, channelName + ".k"));
			vectorRequest.setNumCandidates(channel.getNumCandidates() == null ? request.getNumCandidates() : channel.getNumCandidates());
			vectorRequest.setTrackTotalHits(request.getTrackTotalHits());
			Map<String, Object> vectorBody = vectorSearchBody(index, vectorRequest);
			applySourceExcludes(vectorBody, request.getSourceExcludes(), vectorRequest.getEmbeddingField());
			return vectorBody;
		}
		return keywordSearchBody(request, channel);
	}

	Map<String, Object> vectorSearchBody(VectorSearchRequest request) {
		return vectorSearchBody(null, request);
	}

	Map<String, Object> vectorSearchBody(String index, VectorSearchRequest request) {
		if (request.getQueryVector() == null || request.getQueryVector().isEmpty()) {
			throw new IllegalArgumentException("queryVector must not be empty");
		}
		String embeddingField = request.getEmbeddingField();
		if (embeddingField == null || embeddingField.isBlank()) {
			embeddingField = DEFAULT_EMBEDDING_FIELD;
		}
		int k = HybridSearchMerger.positiveOrDefault(request.getK(), 10, "k");
		int numCandidates = HybridSearchMerger.positiveOrDefault(request.getNumCandidates(), 100, "numCandidates");
		Map<String, Object> body = new LinkedHashMap<>();
		body.put("_source", Map.of("excludes", List.of(embeddingField)));
		body.put("track_total_hits", resolveTrackTotalHits(request.getTrackTotalHits()));
		Map<String, Object> knn = new LinkedHashMap<>();
		knn.put("field", embeddingField);
		knn.put("query_vector", request.getQueryVector());
		knn.put("k", k);
		knn.put("num_candidates", numCandidates);
		if (request.getFilterDsl() != null && !request.getFilterDsl().isEmpty()) {
			knn.put("filter", request.getFilterDsl());
		} else if (documentIndexPolicy.isDocumentIndex(index)) {
			throw new IllegalArgumentException("document vector search requires ACL filterDsl");
		}
		body.put("knn", knn);
		return body;
	}

	Map<String, Object> keywordSearchBody(HybridSearchRequest request) {
		if (request.getKeywordDsl() == null || request.getKeywordDsl().isEmpty()) {
			throw new IllegalArgumentException("keywordDsl must not be empty");
		}
		Map<String, Object> body = new LinkedHashMap<>(request.getKeywordDsl());
		mergeHybridFilters(body, request.getFilters());
		body.put("size", HybridSearchMerger.positiveOrDefault(request.getKeywordK(), 20, "keywordK"));
		body.putIfAbsent("track_total_hits", resolveTrackTotalHits(request.getTrackTotalHits()));
		applySourceExcludes(body, request.getSourceExcludes(), request.getEmbeddingField());
		return body;
	}

	Map<String, Object> keywordSearchBody(HybridSearchRequest request, HybridSearchChannelRequest channel) {
		if (channel.getQueryDsl() == null || channel.getQueryDsl().isEmpty()) {
			throw new IllegalArgumentException(channel.getChannel() + " queryDsl must not be empty");
		}
		Map<String, Object> body = new LinkedHashMap<>(channel.getQueryDsl());
		mergeHybridFilters(body, request.getFilters());
		body.put("size", HybridSearchMerger.positiveOrDefault(channel.getK(), 20, channel.getChannel() + ".k"));
		body.putIfAbsent("track_total_hits", resolveTrackTotalHits(request.getTrackTotalHits()));
		applySourceExcludes(body, request.getSourceExcludes(), request.getEmbeddingField());
		return body;
	}

	void validateHybridRequest(HybridSearchRequest request) {
		validateHybridRequest(null, request);
	}

	void validateHybridRequest(String index, HybridSearchRequest request) {
		if (request == null) {
			throw new IllegalArgumentException("hybrid request must not be null");
		}
		if (documentIndexPolicy.isDocumentIndex(index)
				&& (request.getFilters() == null || request.getFilters().isEmpty())) {
			throw new IllegalArgumentException("document hybrid search requires ACL filters");
		}
		if (request.getChannels() == null || request.getChannels().isEmpty()) {
			throw new IllegalArgumentException("channels must not be empty");
		} else {
			validateChannels(index, request);
		}
		HybridSearchMerger.positiveOrDefault(request.getTopK(), 8, "topK");
		HybridContextWindow contextWindow = request.getContextWindow();
		if (contextWindow != null) {
			nonNegativeOrDefault(contextWindow.getBeforeChunks(), 0, "contextWindow.beforeChunks");
			nonNegativeOrDefault(contextWindow.getAfterChunks(), 0, "contextWindow.afterChunks");
			nonNegativeOrDefault(contextWindow.getMaxContextChars(), 0, "contextWindow.maxContextChars");
		}
	}

	private void validateChannels(String index, HybridSearchRequest request) {
		for (HybridSearchChannelRequest channel : request.getChannels()) {
			String channelName = normalizedChannel(channel.getChannel());
			if (!supportedChannel(channelName)) {
				throw new IllegalArgumentException("unsupported hybrid search channel: " + channel.getChannel());
			}
			if ("DENSE_VECTOR".equals(channelName)) {
				List<Double> vector = channel.getQueryVector() == null ? request.getQueryVector() : channel.getQueryVector();
				if (vector == null || vector.isEmpty()) {
					throw new IllegalArgumentException(channelName + " queryVector must not be empty");
				}
			} else if (channel.getQueryDsl() == null || channel.getQueryDsl().isEmpty()) {
				throw new IllegalArgumentException(channelName + " queryDsl must not be empty");
			}
		}
	}

	private static boolean supportedChannel(String channelName) {
		return "BM25".equals(channelName)
				|| "EXACT".equals(channelName)
				|| "PHRASE".equals(channelName)
				|| "DENSE_VECTOR".equals(channelName);
	}

	private static Map<String, Integer> channelHitCounts(Map<String, List<JsonNode>> hitsByChannel) {
		Map<String, Integer> counts = new LinkedHashMap<>();
		if (hitsByChannel != null) {
			hitsByChannel.forEach((channel, hits) -> counts.put(channel, hits == null ? 0 : hits.size()));
		}
		return counts;
	}

	private static int keywordCount(Map<String, Integer> counts) {
		return counts.entrySet().stream()
				.filter(entry -> "BM25".equals(entry.getKey())
						|| "EXACT".equals(entry.getKey())
						|| "PHRASE".equals(entry.getKey()))
				.mapToInt(Map.Entry::getValue)
				.sum();
	}

	private static int vectorCount(Map<String, Integer> counts) {
		return counts.entrySet().stream()
				.filter(entry -> "DENSE_VECTOR".equals(entry.getKey()))
				.mapToInt(Map.Entry::getValue)
				.sum();
	}

	private static String normalizedChannel(String channel) {
		return channel == null || channel.isBlank()
				? "UNKNOWN"
				: channel.trim().toUpperCase(java.util.Locale.ROOT);
	}

	private void enrichContextWindow(String index, HybridSearchRequest request, List<HybridSearchHit> hits)
			throws IOException {
		HybridContextWindow contextWindow = request.getContextWindow();
		if (contextWindow == null || hits == null || hits.isEmpty()) {
			return;
		}
		int beforeChunks = nonNegativeOrDefault(contextWindow.getBeforeChunks(), 0, "contextWindow.beforeChunks");
		int afterChunks = nonNegativeOrDefault(contextWindow.getAfterChunks(), 0, "contextWindow.afterChunks");
		if (beforeChunks == 0 && afterChunks == 0) {
			return;
		}
		Map<String, Set<Integer>> wanted = wantedContextChunkIndexes(hits, beforeChunks, afterChunks);
		if (wanted.isEmpty()) {
			return;
		}
		Map<String, Map<Integer, String>> contextByDocument = new HashMap<>();
		for (Map.Entry<String, Set<Integer>> entry : wanted.entrySet()) {
			Request contextRequest = new Request("POST", "/" + index + "/_search");
			Map<String, Object> body = contextWindowSearchBody(request, entry.getKey(), entry.getValue());
			contextRequest.setEntity(jsonEntity(objectMapper.writeValueAsString(body)));
			Response contextResponse = restClient.performRequest(contextRequest);
			contextByDocument.put(entry.getKey(), contextChunks(objectMapper.readTree(responseBody(contextResponse))));
		}
		int[] remainingContextChars = { contextWindow.getMaxContextChars() == null ? 0 : contextWindow.getMaxContextChars() };
		boolean unlimited = remainingContextChars[0] <= 0;
		for (HybridSearchHit hit : hits) {
			Map<Integer, String> chunks = contextByDocument.get(hit.getDocumentId());
			if (chunks == null || hit.getChunkIndex() == null) {
				continue;
			}
			hit.setContextBefore(contextValues(chunks, hit.getChunkIndex() - beforeChunks,
					hit.getChunkIndex() - 1, unlimited, remainingContextChars));
			hit.setContextAfter(contextValues(chunks, hit.getChunkIndex() + 1,
					hit.getChunkIndex() + afterChunks, unlimited, remainingContextChars));
		}
	}

	private Map<String, Set<Integer>> wantedContextChunkIndexes(
			List<HybridSearchHit> hits,
			int beforeChunks,
			int afterChunks) {
		Map<String, Set<Integer>> wanted = new LinkedHashMap<>();
		for (HybridSearchHit hit : hits) {
			if (hit.getDocumentId() == null || hit.getDocumentId().isBlank() || hit.getChunkIndex() == null) {
				continue;
			}
			Set<Integer> indexes = wanted.computeIfAbsent(hit.getDocumentId(), ignored -> new LinkedHashSet<>());
			for (int offset = beforeChunks; offset > 0; offset--) {
				int index = hit.getChunkIndex() - offset;
				if (index >= 0) {
					indexes.add(index);
				}
			}
			for (int offset = 1; offset <= afterChunks; offset++) {
				indexes.add(hit.getChunkIndex() + offset);
			}
		}
		return wanted;
	}

	private Map<String, Object> contextWindowSearchBody(
			HybridSearchRequest request,
			String documentId,
			Set<Integer> chunkIndexes) {
		Map<String, Object> body = new LinkedHashMap<>();
		body.put("size", chunkIndexes.size());
		body.put("track_total_hits", false);
		List<Object> filters = new ArrayList<>();
		filters.addAll(filterItems(request.getFilters()));
		filters.add(Map.of("term", Map.of("documentId", documentId)));
		filters.add(Map.of("terms", Map.of("chunkIndex", chunkIndexes)));
		body.put("query", Map.of("bool", Map.of("filter", filters)));
		body.put("sort", List.of(Map.of("chunkIndex", Map.of("order", "asc"))));
		applySourceExcludes(body, request.getSourceExcludes(), request.getEmbeddingField());
		return body;
	}

	private Map<Integer, String> contextChunks(JsonNode root) {
		Map<Integer, String> chunks = new HashMap<>();
		for (JsonNode hit : extractHits(root)) {
			JsonNode source = hit.path("_source");
			JsonNode chunkIndex = source.path("chunkIndex");
			if (!chunkIndex.isInt()) {
				continue;
			}
			String text = firstText(source, "generationText",
					firstText(source, "content", firstText(source, "snippet", null)));
			if (text != null && !text.isBlank()) {
				chunks.put(chunkIndex.asInt(), text);
			}
		}
		return chunks;
	}

	private List<String> contextValues(
			Map<Integer, String> chunks,
			int from,
			int to,
			boolean unlimited,
			int[] remainingContextChars) {
		if (from > to) {
			return List.of();
		}
		List<String> values = new ArrayList<>();
		for (int index = from; index <= to; index++) {
			String value = chunks.get(index);
			if (value == null || value.isBlank()) {
				continue;
			}
			String limited = takeContext(value, unlimited, remainingContextChars);
			if (limited == null || limited.isBlank()) {
				break;
			}
			values.add(limited);
		}
		return values;
	}

	private String takeContext(String value, boolean unlimited, int[] remainingContextChars) {
		if (unlimited) {
			return value;
		}
		if (remainingContextChars[0] <= 0) {
			return "";
		}
		if (value.length() <= remainingContextChars[0]) {
			remainingContextChars[0] -= value.length();
			return value;
		}
		String truncated = value.substring(0, remainingContextChars[0]);
		remainingContextChars[0] = 0;
		return truncated;
	}

	private static void applySourceExcludes(Map<String, Object> body, List<String> requestedExcludes, String embeddingField) {
		List<String> excludes = new ArrayList<>();
		if (requestedExcludes != null) {
			requestedExcludes.stream()
					.filter(value -> value != null && !value.isBlank())
					.forEach(excludes::add);
		}
		String resolvedEmbeddingField = embeddingField == null || embeddingField.isBlank()
				? DEFAULT_EMBEDDING_FIELD
				: embeddingField;
		if (!excludes.contains(resolvedEmbeddingField)) {
			excludes.add(resolvedEmbeddingField);
		}
		body.put("_source", Map.of("excludes", excludes));
	}

	@SuppressWarnings("unchecked")
	private void mergeHybridFilters(Map<String, Object> body, Map<String, Object> filters) {
		if (filters == null || filters.isEmpty()) {
			return;
		}
		Object query = body.get("query");
		Map<String, Object> bool;
		if (query instanceof Map<?, ?> queryMap && queryMap.get("bool") instanceof Map<?, ?> boolMap) {
			bool = new LinkedHashMap<>((Map<String, Object>) boolMap);
		} else {
			bool = new LinkedHashMap<>();
			bool.put("must", query == null ? List.of(Map.of("match_all", Map.of())) : List.of(query));
		}
		List<Object> merged = new ArrayList<>();
		Object existingFilter = bool.get("filter");
		if (existingFilter instanceof List<?> list) {
			merged.addAll(list);
		} else if (existingFilter != null) {
			merged.add(existingFilter);
		}
		merged.addAll(filterItems(filters));
		bool.put("filter", merged);
		body.put("query", Map.of("bool", bool));
	}

	@SuppressWarnings("unchecked")
	private List<Object> filterItems(Map<String, Object> filter) {
		if (filter == null || filter.isEmpty()) {
			return List.of();
		}
		Object bool = filter.get("bool");
		if (bool instanceof Map<?, ?> boolMap) {
			Object items = boolMap.get("filter");
			if (items instanceof List<?> list) {
				return list.stream().map(item -> (Object) item).toList();
			}
			if (items != null) {
				return List.of(items);
			}
		}
		return List.of(filter);
	}

	private static List<JsonNode> extractHits(JsonNode root) {
		JsonNode hitsNode = root.path("hits").path("hits");
		if (!hitsNode.isArray()) {
			return List.of();
		}
		List<JsonNode> hits = new ArrayList<>();
		hitsNode.forEach(hits::add);
		return hits;
	}

	private static int nonNegativeOrDefault(Integer value, int defaultValue, String name) {
		int resolved = value == null ? defaultValue : value;
		if (resolved < 0) {
			throw new IllegalArgumentException(name + " must not be negative");
		}
		return resolved;
	}

	private static String firstText(JsonNode source, String field, String fallback) {
		JsonNode value = source.path(field);
		if (value.isMissingNode() || value.isNull()) {
			return fallback;
		}
		String text = value.asText();
		return text == null || text.isBlank() ? fallback : text;
	}

	String applyDefaultTrackTotalHits(String queryDsl) {
		if (queryDsl == null || queryDsl.isBlank()) {
			throw new IllegalArgumentException("query DSL must not be blank");
		}
		JsonNode root;
		try {
			root = objectMapper.readTree(queryDsl);
		} catch (IOException e) {
			throw new IllegalArgumentException("query DSL must be a valid JSON object", e);
		}
		if (!(root instanceof ObjectNode queryBody)) {
			throw new IllegalArgumentException("query DSL must be a JSON object");
		}
		if (!queryBody.hasNonNull("track_total_hits")) {
			queryBody.put("track_total_hits", properties.getTotalHitsThreshold());
		}
		return queryBody.toString();
	}

	int resolveTrackTotalHits(Integer requestedThreshold) {
		if (requestedThreshold == null) {
			return properties.getTotalHitsThreshold();
		}
		if (requestedThreshold < 1) {
			throw new IllegalArgumentException("trackTotalHits must be greater than 0");
		}
		return requestedThreshold;
	}

	/**
	 * 删除业务数据。
	 */
	private void deleteIndexIfExists(String index) throws IOException {
		Request existsRequest = new Request("HEAD", "/" + index);
		try {
			Response response = restClient.performRequest(existsRequest);
			if (response.getStatusLine().getStatusCode() == 404) {
				return;
			}
		} catch (ResponseException e) {
			if (e.getResponse().getStatusLine().getStatusCode() == 404) {
				return;
			}
			throw e;
		}
		Request deleteRequest = new Request("DELETE", "/" + index);
		restClient.performRequest(deleteRequest);
	}

	/**
	 * 构建请求或领域对象。
	 */
	private String buildBulkBody(String index, String idField, List<Map<String, Object>> documents) throws IOException {
		if (documents == null || documents.isEmpty()) {
			throw new IllegalArgumentException("documents must not be empty");
		}
		StringBuilder body = new StringBuilder();
		for (Map<String, Object> document : documents) {
			Object id = idField == null || idField.isBlank() ? null : document.get(idField);
			body.append("{\"index\":{\"_index\":\"").append(index).append("\"");
			if (id != null) {
				body.append(",\"_id\":").append(objectMapper.writeValueAsString(String.valueOf(id)));
			}
			body.append("}}\n");
			body.append(objectMapper.writeValueAsString(document)).append("\n");
		}
		return body.toString();
	}

	private void validateDocumentChunkIfNeeded(String index, Map<String, Object> document) {
		if (documentIndexPolicy.isDocumentIndex(index)) {
			chunkSchemaValidator.validate(index, document);
		}
	}

	/**
	 * 处理 jsonEntity 相关逻辑。
	 */
	private HttpEntity jsonEntity(String json) {
		return new NStringEntity(json, ContentType.APPLICATION_JSON);
	}

	/**
	 * 构建接口响应对象。
	 */
	private String responseBody(Response response) throws IOException {
		byte[] bs = response.getEntity().getContent().readAllBytes();
		String content = new String(bs);
		return content;
	}
}
