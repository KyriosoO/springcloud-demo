package com.dylan.esquery.api.model;

import java.util.List;

/**
 * 搜索聚合请求，描述分组字段、指标和每层分组返回数量。
 */
public class SearchAggregate {
	private List<String> groupBy;
	private List<SearchMetric> metrics;
	private Integer bucketSize;

	public List<String> getGroupBy() {
		return groupBy;
	}

	public void setGroupBy(List<String> groupBy) {
		this.groupBy = groupBy;
	}

	public List<SearchMetric> getMetrics() {
		return metrics;
	}

	public void setMetrics(List<SearchMetric> metrics) {
		this.metrics = metrics;
	}

	public Integer getBucketSize() {
		return bucketSize;
	}

	public void setBucketSize(Integer bucketSize) {
		this.bucketSize = bucketSize;
	}
}
