package com.dylan.esquery.api.model;

import java.util.List;
import java.util.Map;

/**
 * 源数据分页响应，承载索引服务拉取的一批源文档。
 */
public class SourcePageResponse {
	private List<Map<String, Object>> documents;
	private boolean hasMore;
	private String nextCursor;

	public List<Map<String, Object>> getDocuments() {
		return documents;
	}

	public void setDocuments(List<Map<String, Object>> documents) {
		this.documents = documents;
	}

	public boolean isHasMore() {
		return hasMore;
	}

	public void setHasMore(boolean hasMore) {
		this.hasMore = hasMore;
	}

	public String getNextCursor() {
		return nextCursor;
	}

	public void setNextCursor(String nextCursor) {
		this.nextCursor = nextCursor;
	}
}
