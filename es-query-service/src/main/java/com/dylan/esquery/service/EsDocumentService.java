package com.dylan.esquery.service;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.apache.http.HttpEntity;
import org.apache.http.entity.ContentType;
import org.apache.http.nio.entity.NStringEntity;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.ResponseException;
import org.elasticsearch.client.RestClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import com.dylan.esquery.api.model.HybridRetrievalDiagnostics;
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
		Request keywordRequest = new Request("POST", "/" + index + "/_search");
		keywordRequest.setEntity(jsonEntity(objectMapper.writeValueAsString(keywordSearchBody(request))));
		Response keywordResponse = restClient.performRequest(keywordRequest);

		VectorSearchRequest vectorRequest = new VectorSearchRequest();
		vectorRequest.setEmbeddingField(request.getEmbeddingField());
		vectorRequest.setQueryVector(request.getQueryVector());
		vectorRequest.setFilterDsl(request.getFilters());
		vectorRequest.setK(HybridSearchMerger.positiveOrDefault(request.getVectorK(), 20, "vectorK"));
		vectorRequest.setNumCandidates(request.getNumCandidates());
		vectorRequest.setTrackTotalHits(request.getTrackTotalHits());
		Request vectorEsRequest = new Request("POST", "/" + index + "/_search");
		Map<String, Object> vectorBody = vectorSearchBody(index, vectorRequest);
		applySourceExcludes(vectorBody, request.getSourceExcludes(), vectorRequest.getEmbeddingField());
		vectorEsRequest.setEntity(jsonEntity(objectMapper.writeValueAsString(vectorBody)));
		Response vectorResponse = restClient.performRequest(vectorEsRequest);

		List<JsonNode> keywordHits = extractHits(objectMapper.readTree(responseBody(keywordResponse)));
		List<JsonNode> vectorHits = extractHits(objectMapper.readTree(responseBody(vectorResponse)));
		List<HybridSearchHit> hits = hybridSearchMerger.merge(keywordHits, vectorHits, request);
		HybridRetrievalDiagnostics diagnostics = new HybridRetrievalDiagnostics();
		diagnostics.setKeywordHitCount(keywordHits.size());
		diagnostics.setVectorHitCount(vectorHits.size());
		diagnostics.setReturnedHitCount(hits.size());
		diagnostics.setFusionStrategy("RRF");
		diagnostics.setDegraded(false);
		HybridSearchResponse response = new HybridSearchResponse();
		response.setHits(hits);
		response.setDiagnostics(diagnostics);
		response.setPartial(false);
		return response;
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

	void validateHybridRequest(HybridSearchRequest request) {
		validateHybridRequest(null, request);
	}

	void validateHybridRequest(String index, HybridSearchRequest request) {
		if (request == null) {
			throw new IllegalArgumentException("hybrid request must not be null");
		}
		if (request.getQueryVector() == null || request.getQueryVector().isEmpty()) {
			throw new IllegalArgumentException("queryVector must not be empty");
		}
		if (documentIndexPolicy.isDocumentIndex(index)
				&& (request.getFilters() == null || request.getFilters().isEmpty())) {
			throw new IllegalArgumentException("document hybrid search requires ACL filters");
		}
		keywordSearchBody(request);
		HybridSearchMerger.positiveOrDefault(request.getTopK(), 8, "topK");
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
