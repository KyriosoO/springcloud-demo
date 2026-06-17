package com.dylan.esquery.api.model;

import java.util.Map;

/**
 * 索引重建请求，描述源服务、目标索引和批处理参数。
 */
public class RebuildRequest {
	private String sourceUrl;
	private String targetIndex;
	private String idField;
	private String cursor;
	private String since;
	private Integer batchSize;
	private Map<String, Object> indexDefinition;
	private Map<String, Object> sourceParams;

	public String getSourceUrl() {
		return sourceUrl;
	}

	public void setSourceUrl(String sourceUrl) {
		this.sourceUrl = sourceUrl;
	}

	public String getTargetIndex() {
		return targetIndex;
	}

	public void setTargetIndex(String targetIndex) {
		this.targetIndex = targetIndex;
	}

	public String getIdField() {
		return idField;
	}

	public void setIdField(String idField) {
		this.idField = idField;
	}

	public String getCursor() {
		return cursor;
	}

	public void setCursor(String cursor) {
		this.cursor = cursor;
	}

	public String getSince() {
		return since;
	}

	public void setSince(String since) {
		this.since = since;
	}

	public Integer getBatchSize() {
		return batchSize;
	}

	public void setBatchSize(Integer batchSize) {
		this.batchSize = batchSize;
	}

	public Map<String, Object> getIndexDefinition() {
		return indexDefinition;
	}

	public void setIndexDefinition(Map<String, Object> indexDefinition) {
		this.indexDefinition = indexDefinition;
	}

	public Map<String, Object> getSourceParams() {
		return sourceParams;
	}

	public void setSourceParams(Map<String, Object> sourceParams) {
		this.sourceParams = sourceParams;
	}
}
