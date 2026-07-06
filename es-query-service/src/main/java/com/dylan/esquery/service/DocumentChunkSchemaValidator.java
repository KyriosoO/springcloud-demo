package com.dylan.esquery.service;

import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

/** 校验写入文档索引的 chunk 文档是否包含安全投影字段。 */
@Component
public class DocumentChunkSchemaValidator {

	private static final List<String> REQUIRED_FIELDS = List.of(
			"tenantId", "corpusId", "documentId", "documentVersion", "chunkId",
			"chunkIndex", "charStart", "charEnd", "title", "content", "snippet",
			"aclRef", "aclVersion", "visibility", "status", "indexVersion", "contentHash");
	private static final List<String> STATUSES = List.of("ACTIVE", "REVOKED", "DELETED", "EXPIRED", "BLOCKED");
	private static final List<String> VISIBILITIES = List.of("TENANT", "USER", "DEPARTMENT", "ROLE", "ATTRIBUTE", "PUBLIC");

	public void validate(String index, Map<String, Object> document) {
		if (document == null || document.isEmpty()) {
			throw new IllegalArgumentException("document chunk must not be empty");
		}
		for (String field : REQUIRED_FIELDS) {
			if (isBlankValue(document.get(field))) {
				throw new IllegalArgumentException("document chunk missing required field: " + field);
			}
		}
		String status = String.valueOf(document.get("status"));
		if (!STATUSES.contains(status)) {
			throw new IllegalArgumentException("document chunk status is invalid: " + status);
		}
		String visibility = String.valueOf(document.get("visibility"));
		if (!VISIBILITIES.contains(visibility)) {
			throw new IllegalArgumentException("document chunk visibility is invalid: " + visibility);
		}
		validateVisibilityProjection(visibility, document);
		if (Boolean.TRUE.equals(document.get("chunkAclOverride"))) {
			validateOverrideProjection(document);
		}
	}

	private void validateVisibilityProjection(String visibility, Map<String, Object> document) {
		switch (visibility) {
			case "USER" -> requireNonEmptyList(document, "userIds");
			case "DEPARTMENT" -> requireNonEmptyList(document, "departmentIds");
			case "ROLE" -> requireNonEmptyList(document, "roleIds");
			case "ATTRIBUTE" -> requireNonEmptyList(document, "attributeKeys");
			default -> {
			}
		}
	}

	private void validateOverrideProjection(Map<String, Object> document) {
		if (isBlankValue(document.get("aclRef")) || isBlankValue(document.get("aclVersion"))
				|| isBlankValue(document.get("visibility"))) {
			throw new IllegalArgumentException("chunk ACL override requires full ACL projection");
		}
	}

	private static void requireNonEmptyList(Map<String, Object> document, String field) {
		Object value = document.get(field);
		if (!(value instanceof List<?> list) || list.isEmpty()) {
			throw new IllegalArgumentException("document chunk visibility requires non-empty " + field);
		}
	}

	private static boolean isBlankValue(Object value) {
		return value == null || (value instanceof String text && text.isBlank());
	}
}
