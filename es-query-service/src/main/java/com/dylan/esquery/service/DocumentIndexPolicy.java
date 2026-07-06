package com.dylan.esquery.service;

import com.dylan.esquery.config.EsQueryProperties;
import org.springframework.stereotype.Component;

/** 判断索引或 alias 是否属于 Agent 文档索引。 */
@Component
public class DocumentIndexPolicy {

	private final EsQueryProperties properties;

	public DocumentIndexPolicy(EsQueryProperties properties) {
		this.properties = properties;
	}

	public boolean isDocumentIndex(String indexOrAlias) {
		if (indexOrAlias == null || indexOrAlias.isBlank()) {
			return false;
		}
		return properties.getDocumentIndexPrefixes().stream()
				.filter(prefix -> prefix != null && !prefix.isBlank())
				.anyMatch(indexOrAlias::startsWith);
	}
}
