package com.dylan.esquery.api.model;

import java.util.List;
import java.util.Map;

/**
 * 混合检索单路召回请求。
 */
public class HybridSearchChannelRequest {
	private String channel;
	private Map<String, Object> queryDsl;
	private List<Double> queryVector;
	private String embeddingField;
	private Integer k;
	private Integer numCandidates;
	private Double weight;

	public String getChannel() { return channel; }
	public void setChannel(String channel) { this.channel = channel; }
	public Map<String, Object> getQueryDsl() { return queryDsl; }
	public void setQueryDsl(Map<String, Object> queryDsl) { this.queryDsl = queryDsl; }
	public List<Double> getQueryVector() { return queryVector; }
	public void setQueryVector(List<Double> queryVector) { this.queryVector = queryVector; }
	public String getEmbeddingField() { return embeddingField; }
	public void setEmbeddingField(String embeddingField) { this.embeddingField = embeddingField; }
	public Integer getK() { return k; }
	public void setK(Integer k) { this.k = k; }
	public Integer getNumCandidates() { return numCandidates; }
	public void setNumCandidates(Integer numCandidates) { this.numCandidates = numCandidates; }
	public Double getWeight() { return weight; }
	public void setWeight(Double weight) { this.weight = weight; }
}
