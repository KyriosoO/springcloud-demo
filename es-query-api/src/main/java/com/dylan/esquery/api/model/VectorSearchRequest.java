package com.dylan.esquery.api.model;

import java.util.List;
import java.util.Map;

/**
 * 向量检索请求，描述查询文本、向量字段和召回参数。
 */
public class VectorSearchRequest {
	private String embeddingField;
	private List<Double> queryVector;
	private Map<String, Object> filter;
	private Integer k;
	private Integer numCandidates;
	private Integer trackTotalHits;

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

	public Map<String, Object> getFilter() {
		return filter;
	}

	public void setFilter(Map<String, Object> filter) {
		this.filter = filter;
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

	public Integer getTrackTotalHits() {
		return trackTotalHits;
	}

	public void setTrackTotalHits(Integer trackTotalHits) {
		this.trackTotalHits = trackTotalHits;
	}
}
