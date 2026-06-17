package com.dylan.esquery.api.model;

import java.util.List;

/**
 * 向量检索请求，描述查询文本、向量字段和召回参数。
 */
public class VectorSearchRequest {
	private String embeddingField;
	private List<Double> queryVector;
	private Integer k;
	private Integer numCandidates;

	public String getEmbeddingField() {
		return embeddingField;
	}

	public void setEmbeddingField(String embeddingField) {
		this.embeddingField = embeddingField;
	}

	public List<Double> getQueryVector() {
		return queryVector;
	}

	public void setQueryVector(List<Double> queryVector) {
		this.queryVector = queryVector;
	}

	public Integer getK() {
		return k;
	}

	public void setK(Integer k) {
		this.k = k;
	}

	public Integer getNumCandidates() {
		return numCandidates;
	}

	public void setNumCandidates(Integer numCandidates) {
		this.numCandidates = numCandidates;
	}
}
