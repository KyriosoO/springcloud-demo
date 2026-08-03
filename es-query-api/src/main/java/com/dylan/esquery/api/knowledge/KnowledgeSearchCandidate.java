package com.dylan.esquery.api.knowledge;

import java.time.LocalDate;

public record KnowledgeSearchCandidate(
		String documentId,
		String chunkId,
		String logicalDomainId,
		String title,
		String content,
		String sourceUrl,
		String documentNumber,
		LocalDate writtenDate,
		String materialType,
		int sourceRank,
		String contentSha256,
		String policyRef) {
}
