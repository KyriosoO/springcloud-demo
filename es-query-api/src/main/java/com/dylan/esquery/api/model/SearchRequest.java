package com.dylan.esquery.api.model;

import java.util.List;

/**
 * 通用关键词搜索请求，承载分页、关键字和过滤条件。
 */
public class SearchRequest {
	/**
	 * 关键词查询文本。
	 */
	private String keyword;
	/**
	 * 分页起始位置。
	 */
	private Integer from;
	/**
	 * 返回记录数量。
	 */
	private Integer size;
	/**
	 * 结构化过滤条件列表。
	 */
	private List<SearchFilter> filters;

	public String getKeyword() {
		return keyword;
	}

	public void setKeyword(String keyword) {
		this.keyword = keyword;
	}

	public Integer getFrom() {
		return from;
	}

	public void setFrom(Integer from) {
		this.from = from;
	}

	public Integer getSize() {
		return size;
	}

	public void setSize(Integer size) {
		this.size = size;
	}

	public List<SearchFilter> getFilters() {
		return filters;
	}

	public void setFilters(List<SearchFilter> filters) {
		this.filters = filters;
	}
}
