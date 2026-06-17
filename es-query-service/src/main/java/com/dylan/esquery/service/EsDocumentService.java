package com.dylan.esquery.service;

import java.io.IOException;
import java.util.List;
import java.util.Map;

import org.apache.http.HttpEntity;
import org.apache.http.entity.ContentType;
import org.apache.http.nio.entity.NStringEntity;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.ResponseException;
import org.elasticsearch.client.RestClient;
import org.springframework.stereotype.Service;

import com.dylan.esquery.api.model.VectorSearchRequest;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * ES 文档服务，封装 Elasticsearch 文档写入、删除和查询逻辑。
 */
@Service
public class EsDocumentService {
	private final RestClient restClient;
	private final ObjectMapper objectMapper;

	/**
	 * 创建 EsDocumentService 实例并注入所需依赖。
	 */
	public EsDocumentService(RestClient restClient, ObjectMapper objectMapper) {
		this.restClient = restClient;
		this.objectMapper = objectMapper;
	}

	/**
	 * 执行领域搜索。
	 */
	public String search(String index, String queryDsl) throws IOException {
		Request request = new Request("POST", "/" + index + "/_search");
		request.setEntity(jsonEntity(queryDsl));
		Response response = restClient.performRequest(request);
		return responseBody(response);
	}

	/**
	 * 处理 indexDocument 相关逻辑。
	 */
	public String indexDocument(String index, String id, Map<String, Object> document) throws IOException {
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
		String embeddingField = request.getEmbeddingField();
		if (embeddingField == null || embeddingField.isBlank()) {
			embeddingField = "embedding";
		}

		int k = request.getK() == null ? 10 : request.getK();
		int numCandidates = request.getNumCandidates() == null ? 100 : request.getNumCandidates();
		Map<String, Object> body = Map.of(
				"_source", Map.of("excludes", List.of(embeddingField)),
				"knn", Map.of("field", embeddingField, "query_vector",
						request.getQueryVector(), "k", k, "num_candidates", numCandidates));
		Request esRequest = new Request("POST", "/" + index + "/_search");
		esRequest.setEntity(jsonEntity(objectMapper.writeValueAsString(body)));
		Response response = restClient.performRequest(esRequest);
		return responseBody(response);
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
