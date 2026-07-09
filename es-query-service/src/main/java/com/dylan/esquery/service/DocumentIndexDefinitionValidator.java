package com.dylan.esquery.service;

import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

/** 校验文档索引 mapping 是否具备 ACL、chunk 和 embedding 基础字段。 */
@Component
public class DocumentIndexDefinitionValidator {

	private static final List<String> REQUIRED_FIELDS = List.of(
			"tenantId", "corpusId", "documentId", "documentVersion", "chunkId",
			"chunkIndex", "charStart", "charEnd", "title", "content", "snippet",
			"aclRef", "aclVersion", "visibility", "departmentIds", "roleIds", "userIds",
			"attributeKeys", "status", "indexVersion", "contentHash");
	private static final List<String> FILTER_FIELDS = List.of(
			"tenantId", "corpusId", "documentId", "chunkId", "aclRef", "aclVersion", "status");
	private static final List<String> V2_REQUIRED_FIELDS = List.of(
			"domain", "materialType", "retrievalProfile", "section", "documentNo", "issuer",
			"taxType", "effectiveDate", "validityStatus", "chunkStrategy", "chunkVersion",
			"parentSectionId", "embedding");
	private static final List<String> V2_MARKER_FIELDS = List.of(
			"domain", "materialType", "retrievalProfile", "chunkStrategy", "chunkVersion");
	private static final List<String> V2_FILTER_FIELDS = List.of(
			"domain", "materialType", "retrievalProfile", "documentNo", "issuer", "taxType",
			"validityStatus", "chunkStrategy", "chunkVersion");
	private static final List<String> V2_TEXT_FIELDS = List.of("title", "content", "snippet", "section");
	private static final List<String> V2_EXACT_FIELDS = List.of("title", "section");
	private static final List<String> ALLOWED_ANALYZERS = List.of(
			"standard", "policy_text_analyzer", "policy_phrase_analyzer");

	public void validate(String index, Map<String, Object> indexDefinition) {
		if (indexDefinition == null || indexDefinition.isEmpty()) {
			throw new IllegalArgumentException("document indexDefinition must not be empty");
		}
		Map<?, ?> properties = mappingProperties(indexDefinition);
		for (String field : REQUIRED_FIELDS) {
			if (!properties.containsKey(field)) {
				throw new IllegalArgumentException("document index mapping missing required field: " + field);
			}
		}
		boolean v2 = isV2IndexDefinition(index, properties);
		if (v2) {
			for (String field : V2_REQUIRED_FIELDS) {
				if (!properties.containsKey(field)) {
					throw new IllegalArgumentException("document v2 index mapping missing required field: " + field);
				}
			}
		}
		for (String field : FILTER_FIELDS) {
			if (!isFilterableKeyword(properties.get(field))) {
				throw new IllegalArgumentException("document index mapping field must be keyword-filterable: " + field);
			}
		}
		if (v2) {
			for (String field : V2_FILTER_FIELDS) {
				if (!isFilterableKeyword(properties.get(field))) {
					throw new IllegalArgumentException("document v2 index mapping field must be keyword-filterable: " + field);
				}
			}
			validateV2TextFields(properties);
			validateV2Analyzers(indexDefinition, properties);
		}
		Object embedding = properties.get("embedding");
		if (embedding != null) {
			validateEmbedding(embedding);
		}
	}

	private boolean isV2IndexDefinition(String index, Map<?, ?> properties) {
		if (index != null && index.toLowerCase().contains("-v2")) {
			return true;
		}
		return V2_MARKER_FIELDS.stream().anyMatch(properties::containsKey);
	}

	private boolean isFilterableKeyword(Object mapping) {
		if (!(mapping instanceof Map<?, ?> mappingMap)) {
			return false;
		}
		Object type = mappingMap.get("type");
		if ("keyword".equals(type)) {
			return true;
		}
		Object fields = mappingMap.get("fields");
		return fields instanceof Map<?, ?> fieldsMap && fieldsMap.containsKey("keyword");
	}

	private void validateEmbedding(Object embedding) {
		if (!(embedding instanceof Map<?, ?> embeddingMap)) {
			throw new IllegalArgumentException("document embedding mapping must be an object");
		}
		if (!"dense_vector".equals(embeddingMap.get("type"))) {
			throw new IllegalArgumentException("document embedding type must be dense_vector");
		}
		Object dims = embeddingMap.get("dims");
		if (!(dims instanceof Number number) || number.intValue() <= 0) {
			throw new IllegalArgumentException("document embedding dims must be positive");
		}
	}

	private void validateV2TextFields(Map<?, ?> properties) {
		for (String field : V2_TEXT_FIELDS) {
			if (!isTextField(properties.get(field))) {
				throw new IllegalArgumentException("document v2 index mapping field must be text: " + field);
			}
		}
		for (String field : V2_EXACT_FIELDS) {
			if (!hasKeywordSubfield(properties.get(field))) {
				throw new IllegalArgumentException("document v2 index mapping field must expose keyword subfield: " + field);
			}
		}
	}

	private boolean isTextField(Object mapping) {
		return mapping instanceof Map<?, ?> mappingMap && "text".equals(mappingMap.get("type"));
	}

	private boolean hasKeywordSubfield(Object mapping) {
		if (!(mapping instanceof Map<?, ?> mappingMap)) {
			return false;
		}
		Object fields = mappingMap.get("fields");
		if (!(fields instanceof Map<?, ?> fieldsMap)) {
			return false;
		}
		Object keyword = fieldsMap.get("keyword");
		return keyword instanceof Map<?, ?> keywordMap && "keyword".equals(keywordMap.get("type"));
	}

	private void validateV2Analyzers(Map<String, Object> indexDefinition, Map<?, ?> properties) {
		for (Map.Entry<?, ?> entry : properties.entrySet()) {
			if (entry.getValue() instanceof Map<?, ?> fieldMapping) {
				validateAnalyzerName(fieldMapping.get("analyzer"), String.valueOf(entry.getKey()));
				validateAnalyzerName(fieldMapping.get("search_analyzer"), String.valueOf(entry.getKey()));
			}
		}
		Object settings = indexDefinition.get("settings");
		if (!(settings instanceof Map<?, ?> settingsMap)) {
			return;
		}
		Object analysis = settingsMap.get("analysis");
		if (!(analysis instanceof Map<?, ?> analysisMap)) {
			return;
		}
		Object analyzer = analysisMap.get("analyzer");
		if (analyzer instanceof Map<?, ?> analyzerMap) {
			for (Object name : analyzerMap.keySet()) {
				validateAnalyzerName(name, "settings.analysis.analyzer");
			}
		}
	}

	private void validateAnalyzerName(Object analyzer, String field) {
		if (analyzer == null) {
			return;
		}
		String analyzerName = String.valueOf(analyzer);
		if (!ALLOWED_ANALYZERS.contains(analyzerName)) {
			throw new IllegalArgumentException("document v2 index analyzer is not allowed for " + field + ": " + analyzerName);
		}
	}

	@SuppressWarnings("unchecked")
	private Map<?, ?> mappingProperties(Map<String, Object> indexDefinition) {
		Object mappings = indexDefinition.get("mappings");
		if (!(mappings instanceof Map<?, ?> mappingMap)) {
			throw new IllegalArgumentException("document indexDefinition.mappings must be an object");
		}
		Object properties = mappingMap.get("properties");
		if (!(properties instanceof Map<?, ?> propertyMap)) {
			throw new IllegalArgumentException("document indexDefinition.mappings.properties must be an object");
		}
		return (Map<?, ?>) propertyMap;
	}
}
