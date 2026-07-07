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
		for (String field : FILTER_FIELDS) {
			if (!isFilterableKeyword(properties.get(field))) {
				throw new IllegalArgumentException("document index mapping field must be keyword-filterable: " + field);
			}
		}
		Object embedding = properties.get("embedding");
		if (embedding != null) {
			validateEmbedding(embedding);
		}
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
