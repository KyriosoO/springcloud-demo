package com.dylan.esquery.service;

public record KnowledgeReadDecision(
		String logicalDomainId,
		String retrievalProfileId,
		String profileVersion,
		String readPolicyVersion,
		String decisionId) {
}
