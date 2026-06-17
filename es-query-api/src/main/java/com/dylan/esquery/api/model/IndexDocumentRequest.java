package com.dylan.esquery.api.model;

import java.util.Map;

/**
 * 单文档索引请求，承载目标索引、文档 ID 和文档内容。
 */
public class IndexDocumentRequest {
	private String id;
	private Map<String, Object> document;

	public String getId() {
		return id;
	}

	public void setId(String id) {
		this.id = id;
	}

	public Map<String, Object> getDocument() {
		return document;
	}

	public void setDocument(Map<String, Object> document) {
		this.document = document;
	}
}
