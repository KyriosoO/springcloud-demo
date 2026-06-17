package com.dylan.employee.es;

/**
 * 员工索引重建请求，承载重建参数。
 */
public class EmployeeRebuildRequest {
	private String since;
	private String targetIndex;
	private Integer batchSize;
	private String embeddingField;
	private Integer embeddingDims;

	public String getSince() {
		return since;
	}

	public void setSince(String since) {
		this.since = since;
	}

	public String getTargetIndex() {
		return targetIndex;
	}

	public void setTargetIndex(String targetIndex) {
		this.targetIndex = targetIndex;
	}

	public Integer getBatchSize() {
		return batchSize;
	}

	public void setBatchSize(Integer batchSize) {
		this.batchSize = batchSize;
	}

	public String getEmbeddingField() {
		return embeddingField;
	}

	public void setEmbeddingField(String embeddingField) {
		this.embeddingField = embeddingField;
	}

	public Integer getEmbeddingDims() {
		return embeddingDims;
	}

	public void setEmbeddingDims(Integer embeddingDims) {
		this.embeddingDims = embeddingDims;
	}
}
