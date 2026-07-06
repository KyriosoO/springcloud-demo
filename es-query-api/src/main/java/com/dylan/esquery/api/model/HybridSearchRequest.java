package com.dylan.esquery.api.model;

import java.util.List;
import java.util.Map;

/**
 * 混合检索请求，queryVector 由上游生成，es-query 只负责检索与融合。
 */
public class HybridSearchRequest {
	private String queryText;
	private Map<String, Object> keywordDsl;
	private Map<String, Object> filters;
	private List<Double> queryVector;
	private String embeddingField;
	private Integer keywordK;
	private Integer vectorK;
	private Integer topK;
	private Integer numCandidates;
	private Integer rrfK;
	private List<String> sourceExcludes;
	private HybridContextWindow contextWindow;
	private Integer trackTotalHits;

	public String getQueryText() { return queryText; }
	public void setQueryText(String queryText) { this.queryText = queryText; }
	public Map<String, Object> getKeywordDsl() { return keywordDsl; }
	public void setKeywordDsl(Map<String, Object> keywordDsl) { this.keywordDsl = keywordDsl; }
	public Map<String, Object> getFilters() { return filters; }
	public void setFilters(Map<String, Object> filters) { this.filters = filters; }
	public List<Double> getQueryVector() { return queryVector; }
	public void setQueryVector(List<Double> queryVector) { this.queryVector = queryVector; }
	public String getEmbeddingField() { return embeddingField; }
	public void setEmbeddingField(String embeddingField) { this.embeddingField = embeddingField; }
	public Integer getKeywordK() { return keywordK; }
	public void setKeywordK(Integer keywordK) { this.keywordK = keywordK; }
	public Integer getVectorK() { return vectorK; }
	public void setVectorK(Integer vectorK) { this.vectorK = vectorK; }
	public Integer getTopK() { return topK; }
	public void setTopK(Integer topK) { this.topK = topK; }
	public Integer getNumCandidates() { return numCandidates; }
	public void setNumCandidates(Integer numCandidates) { this.numCandidates = numCandidates; }
	public Integer getRrfK() { return rrfK; }
	public void setRrfK(Integer rrfK) { this.rrfK = rrfK; }
	public List<String> getSourceExcludes() { return sourceExcludes; }
	public void setSourceExcludes(List<String> sourceExcludes) { this.sourceExcludes = sourceExcludes; }
	public HybridContextWindow getContextWindow() { return contextWindow; }
	public void setContextWindow(HybridContextWindow contextWindow) { this.contextWindow = contextWindow; }
	public Integer getTrackTotalHits() { return trackTotalHits; }
	public void setTrackTotalHits(Integer trackTotalHits) { this.trackTotalHits = trackTotalHits; }
}
