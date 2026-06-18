package com.dylan.esquery.api.model;

/**
 * 搜索排序条件。
 */
public class SearchSort {
	private String field;
	private SearchSortDirection direction;

	public String getField() {
		return field;
	}

	public void setField(String field) {
		this.field = field;
	}

	public SearchSortDirection getDirection() {
		return direction;
	}

	public void setDirection(SearchSortDirection direction) {
		this.direction = direction;
	}
}
