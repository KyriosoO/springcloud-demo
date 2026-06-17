package com.dylan.employee.service;

import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.dylan.esquery.api.model.SearchFilter;
import com.dylan.esquery.api.model.SearchRequest;
import com.dylan.esquery.api.model.SemanticSearchRequest;
import com.dylan.employee.es.EmployeeRebuildRequest;
import com.dylan.esquery.api.model.BulkIndexRequest;
import com.dylan.esquery.api.model.IndexDocumentRequest;
import com.dylan.employee.es.EsQueryClient;
import com.dylan.esquery.api.model.RebuildRequest;
import com.dylan.esquery.api.model.RebuildTask;
import com.dylan.esquery.api.model.VectorSearchRequest;
import com.dylan.employee.model.Employee;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * 员工 ES 编排服务，负责员工索引重建和检索调用。
 */
@Service
public class EmployeeEsService {
	private static final String ID_FIELD = "idCardNo";

	private final EmployeeService employeeService;
	private final EmployeeEmbeddingService embeddingService;
	private final EsQueryClient esQueryClient;
	private final ObjectMapper objectMapper;
	private final String index;
	private final String sourceUrl;
	private final int defaultEmbeddingDims;

	/**
	 * 创建 EmployeeEsService 实例并注入所需依赖。
	 */
	public EmployeeEsService(EmployeeService employeeService, EmployeeEmbeddingService embeddingService,
			EsQueryClient esQueryClient, ObjectMapper objectMapper,
			@Value("${employee.es.index:employee}") String index,
			@Value("${employee.es.source-url:http://localhost:9210/internal/es/employees}") String sourceUrl,
			@Value("${employee.embedding.dims:1024}") int defaultEmbeddingDims) {
		this.employeeService = employeeService;
		this.embeddingService = embeddingService;
		this.esQueryClient = esQueryClient;
		this.objectMapper = objectMapper;
		this.index = index;
		this.sourceUrl = sourceUrl;
		this.defaultEmbeddingDims = defaultEmbeddingDims;
	}

	/**
	 * 执行领域搜索。
	 */
	public String search(SearchRequest request) throws JsonProcessingException {
		return esQueryClient.search(index, buildSearchDsl(request));
	}

	public String search(SearchRequest request, String userId) throws JsonProcessingException {
		return search(request);
	}

	/**
	 * 执行向量检索逻辑。
	 */
	public String vectorSearch(SemanticSearchRequest request) {
		SemanticSearchRequest safeRequest = request == null ? new SemanticSearchRequest() : request;
		VectorSearchRequest esRequest = new VectorSearchRequest();
		esRequest.setEmbeddingField(normalizeEmbeddingField(safeRequest.getEmbeddingField()));
		if (safeRequest.getQueryVector() != null && !safeRequest.getQueryVector().isEmpty()) {
			esRequest.setQueryVector(safeRequest.getQueryVector());
		} else {
			esRequest.setQueryVector(embeddingService.embed(safeRequest.getQueryText(), normalizeEmbeddingDims(safeRequest.getEmbeddingDims())));
		}
		esRequest.setK(safeRequest.getK());
		esRequest.setNumCandidates(safeRequest.getNumCandidates());
		return esQueryClient.vectorSearch(index, esRequest);
	}

	/**
	 * 处理 indexOne 相关逻辑。
	 */
	public String indexOne(String idCardNo, String embeddingField, Integer embeddingDims) {
		Employee employee = employeeService.detail(idCardNo);
		IndexDocumentRequest request = new IndexDocumentRequest();
		request.setId(employee.getIdCardNo());
		request.setDocument(employeeService.toEsDocument(employee, embeddingField, embeddingDims));
		return esQueryClient.indexDocument(index, request);
	}

	/**
	 * 删除业务数据。
	 */
	public String deleteOne(String idCardNo) {
		if (idCardNo == null || idCardNo.isBlank()) {
			throw new IllegalArgumentException("idCardNo must not be blank");
		}
		return esQueryClient.deleteDocument(index, idCardNo);
	}

	/**
	 * 批量处理索引文档。
	 */
	public String bulkIndex(int page, int size, String embeddingField, Integer embeddingDims) {
		List<Employee> employees = employeeService.page(page, size);
		BulkIndexRequest request = new BulkIndexRequest();
		request.setIdField(ID_FIELD);
		request.setDocuments(employeeService.toEsDocuments(employees, embeddingField, embeddingDims));
		return esQueryClient.bulkIndex(index, request);
	}

	/**
	 * 处理 fullRebuild 相关逻辑。
	 */
	public RebuildTask fullRebuild(EmployeeRebuildRequest request) {
		return esQueryClient.fullRebuild(index, rebuildRequest(request));
	}

	/**
	 * 处理 incrementalRebuild 相关逻辑。
	 */
	public RebuildTask incrementalRebuild(EmployeeRebuildRequest request) {
		return esQueryClient.incrementalRebuild(index, rebuildRequest(request));
	}

	/**
	 * 处理 task 相关逻辑。
	 */
	public RebuildTask task(String taskId) {
		return esQueryClient.task(taskId);
	}

	/**
	 * 处理 tasks 相关逻辑。
	 */
	public Collection<RebuildTask> tasks() {
		return esQueryClient.tasks();
	}

	/**
	 * 发起或处理索引重建。
	 */
	private RebuildRequest rebuildRequest(EmployeeRebuildRequest request) {
		EmployeeRebuildRequest safeRequest = request == null ? new EmployeeRebuildRequest() : request;
		RebuildRequest esRequest = new RebuildRequest();
		esRequest.setSourceUrl(sourceUrl);
		esRequest.setIdField(ID_FIELD);
		esRequest.setSince(safeRequest.getSince());
		esRequest.setTargetIndex(safeRequest.getTargetIndex());
		esRequest.setBatchSize(safeRequest.getBatchSize());
		esRequest.setIndexDefinition(employeeIndexDefinition(safeRequest));
		if (hasText(safeRequest.getEmbeddingField())) {
			esRequest.setSourceParams(Map.of(
					"embeddingField", safeRequest.getEmbeddingField(),
					"embeddingDims", normalizeEmbeddingDims(safeRequest.getEmbeddingDims())));
		}
		return esRequest;
	}

	/**
	 * 构建请求或领域对象。
	 */
	private String buildSearchDsl(SearchRequest request) throws JsonProcessingException {
		String keyword = request == null ? null : request.getKeyword();
		int from = request == null || request.getFrom() == null ? 0 : request.getFrom();
		int size = request == null || request.getSize() == null ? 20 : request.getSize();
		List<SearchFilter> filters = request == null ? null : request.getFilters();
		Map<String, Object> query = buildQuery(keyword, filters);
		Map<String, Object> dsl = Map.of("_source", Map.of("excludes", List.of("embedding")),
		        "from", from,
		        "size", size,
		        "query", query);
		return objectMapper.writeValueAsString(dsl);
	}

	/**
	 * 构建请求或领域对象。
	 */
	private Map<String, Object> buildQuery(String keyword, List<SearchFilter> filters) {
		List<Map<String, Object>> must = new ArrayList<>();
		if (hasText(keyword)) {
			must.add(Map.of("multi_match", Map.of(
					"query", keyword,
					"type", "phrase",
					"fields", List.of("contactAddress", "chineseName", "idCardNo"))));
		}
		if (filters != null) {
			for (SearchFilter filter : filters) {
				Map<String, Object> clause = filterClause(filter);
				if (clause != null) {
					must.add(clause);
				}
			}
		}
		if (must.isEmpty()) {
			return Map.of("match_all", Map.of());
		}
		if (must.size() == 1) {
			return must.get(0);
		}
		return Map.of("bool", Map.of("must", must));
	}

	/**
	 * 处理 filterClause 相关逻辑。
	 */
	private Map<String, Object> filterClause(SearchFilter filter) {
		if (filter == null || !hasText(filter.getField()) || (!hasText(filter.getValue()) && !hasValues(filter))) {
			return null;
		}
		String field = normalizeFilterField(filter.getField());
		if (field == null) {
			return null;
		}
		String operator = filter.getOperator() == null ? "contains" : filter.getOperator().toLowerCase();
		if (operator.endsWith("any") || hasValues(filter)) {
			return anyFilterClause(field, operator, filterValues(filter));
		}
		String value = filter.getValue();
		if ("startswith".equals(operator) || "starts_with".equals(operator) || "prefix".equals(operator)) {
			return Map.of("prefix", Map.of(exactField(field), value));
		}
		if ("equals".equals(operator) || "eq".equals(operator) || "term".equals(operator)) {
			return Map.of("term", Map.of(exactField(field), value));
		}
		if (isKeywordField(field)) {
			return Map.of("wildcard", Map.of(field, "*" + value + "*"));
		}
		return Map.of("match_phrase", Map.of(field, value));
	}

	/**
	 * 处理 anyFilterClause 相关逻辑。
	 */
	private Map<String, Object> anyFilterClause(String field, String operator, List<String> values) {
		List<Map<String, Object>> should = new ArrayList<>();
		for (String value : values) {
			if (!hasText(value)) {
				continue;
			}
			should.add(singleFilterClause(field, normalizeAnyOperator(operator), value));
		}
		if (should.isEmpty()) {
			return null;
		}
		if (should.size() == 1) {
			return should.get(0);
		}
		return Map.of("bool", Map.of("should", should, "minimum_should_match", 1));
	}

	/**
	 * 处理 singleFilterClause 相关逻辑。
	 */
	private Map<String, Object> singleFilterClause(String field, String operator, String value) {
		if ("startswith".equals(operator) || "starts_with".equals(operator) || "prefix".equals(operator)) {
			return Map.of("prefix", Map.of(exactField(field), value));
		}
		if ("equals".equals(operator) || "eq".equals(operator) || "term".equals(operator)) {
			return Map.of("term", Map.of(exactField(field), value));
		}
		if (isKeywordField(field)) {
			return Map.of("wildcard", Map.of(field, "*" + value + "*"));
		}
		return Map.of("match_phrase", Map.of(field, value));
	}

	/**
	 * 规范化输入值。
	 */
	private String normalizeAnyOperator(String operator) {
		return switch (operator) {
		case "startswithany", "starts_with_any", "prefixany" -> "startswith";
		case "equalsany", "eqany", "termany", "in" -> "equals";
		default -> "contains";
		};
	}

	/**
	 * 处理 filterValues 相关逻辑。
	 */
	private List<String> filterValues(SearchFilter filter) {
		if (hasValues(filter)) {
			return filter.getValues();
		}
		if (hasText(filter.getValue())) {
			return List.of(filter.getValue());
		}
		return List.of();
	}

	/**
	 * 判断是否存在指定条件。
	 */
	private boolean hasValues(SearchFilter filter) {
		return filter.getValues() != null && !filter.getValues().isEmpty();
	}

	/**
	 * 规范化输入值。
	 */
	private String normalizeFilterField(String field) {
		return switch (field) {
		case "contactAddress", "chineseName", "idCardNo", "memberNo", "phoneNo", "email", "position" -> field;
		default -> null;
		};
	}

	/**
	 * 处理 exactField 相关逻辑。
	 */
	private String exactField(String field) {
		if (isKeywordField(field)) {
			return field;
		}
		return field + ".keyword";
	}

	private boolean isKeywordField(String field) {
		return "idCardNo".equals(field) || "memberNo".equals(field) || "phoneNo".equals(field)
				|| "email".equals(field);
	}
	
	/**
	 * 处理 textMapping 相关逻辑。
	 */
	private Map<String, Object> textMapping() {
		return Map.of(
				"type", "text",
				"analyzer", "ik_max_word",
				"search_analyzer", "ik_smart",
				"fields", Map.of("keyword", Map.of("type", "keyword")));
	}
	
	/**
	 * 执行关键词检索逻辑。
	 */
	private Map<String, Object> keywordMapping() {
		return Map.of("type", "keyword");
	}
	
	/**
	 * 处理 employeeIndexDefinition 相关逻辑。
	 */
	private Map<String, Object> employeeIndexDefinition(EmployeeRebuildRequest request) {
		Map<String, Object> properties = new LinkedHashMap<>();
		properties.put("idCardNo", keywordMapping());
		properties.put("memberNo", keywordMapping());
		properties.put("phoneNo", keywordMapping());
		properties.put("email", keywordMapping());
		properties.put("chineseName", textMapping());
		properties.put("contactAddress", textMapping());
		properties.put("position", textMapping());
		properties.put("embeddingText", textMapping());
		if (hasText(request.getEmbeddingField())) {
			properties.put(request.getEmbeddingField(), Map.of(
					"type", "dense_vector",
					"dims", normalizeEmbeddingDims(request.getEmbeddingDims()),
					"index", true,
					"similarity", "cosine"));
		}
		return Map.of("mappings", Map.of("properties", properties));
	}
	
	/**
	 * 规范化输入值。
	 */
	private String normalizeEmbeddingField(String embeddingField) {
		if (embeddingField == null || embeddingField.isBlank()) {
			return "embedding";
		}
		return embeddingField;
	}

	/**
	 * 规范化输入值。
	 */
	private int normalizeEmbeddingDims(Integer embeddingDims) {
		if (embeddingDims == null || embeddingDims <= 0) {
			return defaultEmbeddingDims;
		}
		return embeddingDims;
	}

	/**
	 * 判断是否存在指定条件。
	 */
	private boolean hasText(String value) {
		return value != null && !value.isBlank();
	}
}
