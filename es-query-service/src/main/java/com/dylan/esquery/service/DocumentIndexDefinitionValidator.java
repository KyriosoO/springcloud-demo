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
		Object embedding = properties.get("embedding");
		if (embedding instanceof Map<?, ?> embeddingMap && embeddingMap.containsKey("dims")) {
			Object dims = embeddingMap.get("dims");
			if (!(dims instanceof Number number) || number.intValue() <= 0) {
				throw new IllegalArgumentException("document embedding dims must be positive");
			}
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
