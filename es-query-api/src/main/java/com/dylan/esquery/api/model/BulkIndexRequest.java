package com.dylan.esquery.api.model;

import java.util.List;
import java.util.Map;

/**
 * 批量索引请求，承载目标索引和待写入文档集合。
 */
public class BulkIndexRequest {
	private String idField;
	private List<Map<String, Object>> documents;

	public String getIdField() {
		return idField;
	}

	public void setIdField(String idField) {
		this.idField = idField;
	}

	public List<Map<String, Object>> getDocuments() {
		return documents;
	}

	public void setDocuments(List<Map<String, Object>> documents) {
		this.documents = documents;
	}
}
