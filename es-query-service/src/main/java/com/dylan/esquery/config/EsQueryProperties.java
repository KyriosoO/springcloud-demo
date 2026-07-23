package com.dylan.esquery.config;

import java.util.ArrayList;
import java.util.List;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Elasticsearch 查询策略配置。
 */
@ConfigurationProperties(prefix = "es.query")
public class EsQueryProperties implements InitializingBean {

	private Integer totalHitsThreshold;
	private List<String> rebuildSourceAllowedHosts = new ArrayList<>();
	private Integer rebuildMaxBatchSize = 500;
	private String managementServiceToken;

	public Integer getTotalHitsThreshold() {
		return totalHitsThreshold;
	}

	public void setTotalHitsThreshold(Integer totalHitsThreshold) {
		this.totalHitsThreshold = totalHitsThreshold;
	}

	public List<String> getRebuildSourceAllowedHosts() {
		return rebuildSourceAllowedHosts;
	}

	public void setRebuildSourceAllowedHosts(List<String> rebuildSourceAllowedHosts) {
		List<String> filtered = rebuildSourceAllowedHosts == null ? List.of() : rebuildSourceAllowedHosts.stream()
				.filter(host -> host != null && !host.isBlank())
				.map(host -> host.trim().toLowerCase())
				.toList();
		this.rebuildSourceAllowedHosts = new ArrayList<>(filtered);
	}

	public Integer getRebuildMaxBatchSize() {
		return rebuildMaxBatchSize;
	}

	public void setRebuildMaxBatchSize(Integer rebuildMaxBatchSize) {
		this.rebuildMaxBatchSize = rebuildMaxBatchSize;
	}

	public String getManagementServiceToken() {
		return managementServiceToken;
	}

	public void setManagementServiceToken(String managementServiceToken) {
		this.managementServiceToken = managementServiceToken;
	}

	@Override
	public void afterPropertiesSet() {
		if (totalHitsThreshold == null || totalHitsThreshold < 1) {
			throw new IllegalStateException("es.query.total-hits-threshold must be greater than 0");
		}
		if (rebuildMaxBatchSize == null || rebuildMaxBatchSize < 1) {
			throw new IllegalStateException("es.query.rebuild-max-batch-size must be greater than 0");
		}
		if (rebuildSourceAllowedHosts == null || rebuildSourceAllowedHosts.isEmpty()) {
			throw new IllegalStateException("es.query.rebuild-source-allowed-hosts must not be empty");
		}
	}
}
