package com.dylan.esquery.api.model;

/**
 * 搜索聚合指标。
 */
public class SearchMetric {
	private String field;
	private SearchMetricFunction function;
	private String alias;

	public String getField() {
		return field;
	}

	public void setField(String field) {
		this.field = field;
	}

	public SearchMetricFunction getFunction() {
		return function;
	}

	public void setFunction(SearchMetricFunction function) {
		this.function = function;
	}

	public String getAlias() {
		return alias;
	}

	public void setAlias(String alias) {
		this.alias = alias;
	}
}
