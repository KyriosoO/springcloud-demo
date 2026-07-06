package com.dylan.esquery.api.model;

/**
 * 混合检索诊断信息，不包含查询向量、DSL 或证据正文。
 */
public class HybridRetrievalDiagnostics {
	private Integer keywordHitCount;
	private Integer vectorHitCount;
	private Integer returnedHitCount;
	private String fusionStrategy;
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

	public String getFusionStrategy() {
		return fusionStrategy;
	}

	public void setFusionStrategy(String fusionStrategy) {
		this.fusionStrategy = fusionStrategy;
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
