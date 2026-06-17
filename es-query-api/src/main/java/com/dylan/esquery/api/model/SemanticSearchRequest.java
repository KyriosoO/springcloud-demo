package com.dylan.esquery.api.model;

import java.util.List;

/**
 * 通用语义搜索请求，承载语义文本、查询向量和向量召回参数。
 */
public class SemanticSearchRequest {
	/**
	 * 向量字段名称。
	 */
	private String embeddingField;
	/**
	 * 待向量化的语义查询文本。
	 */
	private String queryText;
	/**
	 * 已生成的查询向量。
	 */
	private List<Double> queryVector;
	/**
	 * 向量维度。
	 */
	private Integer embeddingDims;
	/**
	 * 向量检索返回的近邻数量。
	 */
	private Integer k;
	/**
	 * 向量检索召回候选数量。
	 */
	private Integer numCandidates;

	public String getEmbeddingField() {
		return embeddingField;
	}

	public void setEmbeddingField(String embeddingField) {
		this.embeddingField = embeddingField;
	}

	public String getQueryText() {
		return queryText;
	}

	public void setQueryText(String queryText) {
		this.queryText = queryText;
	}

	public List<Double> getQueryVector() {
		return queryVector;
	}

	public void setQueryVector(List<Double> queryVector) {
		this.queryVector = queryVector;
	}

	public Integer getEmbeddingDims() {
		return embeddingDims;
	}

	public void setEmbeddingDims(Integer embeddingDims) {
		this.embeddingDims = embeddingDims;
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
