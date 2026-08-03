package com.dylan.esquery.api.knowledge;

import java.util.List;

public record KnowledgeSearchResponse(
		int schemaVersion,
		String logicalDomainId,
		String retrievalProfileId,
		String path,
		String profileVersion,
		String indexSnapshotId,
		String readPolicyVersion,
		boolean truncated,
		List<KnowledgeSearchCandidate> candidates) {
	public KnowledgeSearchResponse {
		candidates = List.copyOf(candidates);
	}
}
