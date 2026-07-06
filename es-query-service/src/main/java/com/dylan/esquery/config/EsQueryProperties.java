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
	private List<String> documentIndexPrefixes = new ArrayList<>(List.of("agent-doc-"));

	public Integer getTotalHitsThreshold() {
		return totalHitsThreshold;
	}

	public void setTotalHitsThreshold(Integer totalHitsThreshold) {
		this.totalHitsThreshold = totalHitsThreshold;
	}

	public List<String> getDocumentIndexPrefixes() {
		return documentIndexPrefixes;
	}

	public void setDocumentIndexPrefixes(List<String> documentIndexPrefixes) {
		List<String> filtered = documentIndexPrefixes == null ? List.of() : documentIndexPrefixes.stream()
				.filter(prefix -> prefix != null && !prefix.isBlank())
				.toList();
		this.documentIndexPrefixes = filtered.isEmpty()
				? new ArrayList<>(List.of("agent-doc-"))
				: new ArrayList<>(filtered);
	}

	@Override
	public void afterPropertiesSet() {
		if (totalHitsThreshold == null || totalHitsThreshold < 1) {
			throw new IllegalStateException("es.query.total-hits-threshold must be greater than 0");
		}
	}
}
