package com.dylan.esquery.api.model;

import java.util.Map;

/**
 * 混合检索诊断信息，不包含查询向量、DSL 或证据正文。
 */
public class HybridRetrievalDiagnostics {
	private Integer keywordHitCount;
	private Integer vectorHitCount;
	private Integer returnedHitCount;
	private Integer fusedCandidateCount;
	private Integer dedupedCandidateCount;
	private Integer rrfK;
	private Integer maxChunksPerDocument;
	private String fusionStrategy;
	private Map<String, Integer> channelHitCounts;
	private Map<String, Double> channelWeights;
	private String rerankStatus;
	private String rerankSkippedReason;
	private Boolean degraded;
	private String degradationReason;

	public Integer getKeywordHitCount() {
		return keywordHitCount;
	}

	public void setKeywordHitCount(Integer keywordHitCount) {
		this.keywordHitCount = keywordHitCount;
	}

	public Integer getVectorHitCount() {
		return vectorHitCount;
	}

	public void setVectorHitCount(Integer vectorHitCount) {
		this.vectorHitCount = vectorHitCount;
	}

	public Integer getReturnedHitCount() {
		return returnedHitCount;
	}

	public void setReturnedHitCount(Integer returnedHitCount) {
		this.returnedHitCount = returnedHitCount;
	}

	public Integer getFusedCandidateCount() {
		return fusedCandidateCount;
	}

	public void setFusedCandidateCount(Integer fusedCandidateCount) {
		this.fusedCandidateCount = fusedCandidateCount;
	}

	public Integer getDedupedCandidateCount() {
		return dedupedCandidateCount;
	}

	public void setDedupedCandidateCount(Integer dedupedCandidateCount) {
		this.dedupedCandidateCount = dedupedCandidateCount;
	}

	public Integer getRrfK() {
		return rrfK;
	}

	public void setRrfK(Integer rrfK) {
		this.rrfK = rrfK;
	}

	public Integer getMaxChunksPerDocument() {
		return maxChunksPerDocument;
	}

	public void setMaxChunksPerDocument(Integer maxChunksPerDocument) {
		this.maxChunksPerDocument = maxChunksPerDocument;
	}

	public String getFusionStrategy() {
		return fusionStrategy;
	}

	public void setFusionStrategy(String fusionStrategy) {
		this.fusionStrategy = fusionStrategy;
	}

	public Map<String, Integer> getChannelHitCounts() {
		return channelHitCounts;
	}

	public void setChannelHitCounts(Map<String, Integer> channelHitCounts) {
		this.channelHitCounts = channelHitCounts;
	}

	public Map<String, Double> getChannelWeights() {
		return channelWeights;
	}

	public void setChannelWeights(Map<String, Double> channelWeights) {
		this.channelWeights = channelWeights;
	}

	public String getRerankStatus() {
		return rerankStatus;
	}

	public void setRerankStatus(String rerankStatus) {
		this.rerankStatus = rerankStatus;
	}

	public String getRerankSkippedReason() {
		return rerankSkippedReason;
	}

	public void setRerankSkippedReason(String rerankSkippedReason) {
		this.rerankSkippedReason = rerankSkippedReason;
	}

	public Boolean getDegraded() {
		return degraded;
	}

	public void setDegraded(Boolean degraded) {
		this.degraded = degraded;
	}

	public String getDegradationReason() {
		return degradationReason;
	}

	public void setDegradationReason(String degradationReason) {
		this.degradationReason = degradationReason;
	}
}
