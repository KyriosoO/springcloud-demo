package com.dylan.esquery.api.model;

/**
 * 混合检索上下文窗口配置。
 */
public class HybridContextWindow {
	private Integer beforeChunks;
	private Integer afterChunks;
	private Integer maxContextChars;

	public Integer getBeforeChunks() {
		return beforeChunks;
	}

	public void setBeforeChunks(Integer beforeChunks) {
		this.beforeChunks = beforeChunks;
	}

	public Integer getAfterChunks() {
		return afterChunks;
	}

	public void setAfterChunks(Integer afterChunks) {
		this.afterChunks = afterChunks;
	}

	public Integer getMaxContextChars() {
		return maxContextChars;
	}

	public void setMaxContextChars(Integer maxContextChars) {
		this.maxContextChars = maxContextChars;
	}
}
