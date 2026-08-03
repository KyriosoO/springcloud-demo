package com.dylan.esquery.api.knowledge;

import java.util.List;

public record KnowledgeSearchRequest(
		int schemaVersion,
		String logicalDomainId,
		String retrievalProfileId,
		String path,
		String queryText,
		List<Double> queryVector,
		int limit) {
	public KnowledgeSearchRequest {
		queryVector = queryVector == null ? null : List.copyOf(queryVector);
	}
}
