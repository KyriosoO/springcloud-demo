package com.dylan.esquery.api.model;

import java.util.List;

/**
 * 混合检索响应。
 */
public class HybridSearchResponse {
	private List<HybridSearchHit> hits;
	private HybridRetrievalDiagnostics diagnostics;
	private boolean partial;

	public List<HybridSearchHit> getHits() {
		return hits;
	}

	public void setHits(List<HybridSearchHit> hits) {
		this.hits = hits;
	}

	public HybridRetrievalDiagnostics getDiagnostics() {
		return diagnostics;
	}

	public void setDiagnostics(HybridRetrievalDiagnostics diagnostics) {
		this.diagnostics = diagnostics;
	}

	public boolean isPartial() {
		return partial;
	}

	public void setPartial(boolean partial) {
		this.partial = partial;
	}
}
