package com.dylan.esquery.service;

import java.util.List;

/** gold query 样本，不保存正文以外的权限明细或 provider prompt。 */
public record DocumentGoldQueryCase(
		String caseId,
		String query,
		String domain,
		String materialType,
		String retrievalProfile,
		String profileVersion,
		String goldSetVersion,
		List<String> expectedDocumentIds,
		List<String> deniedDocumentIds,
		List<String> revokedDocumentIds,
		int topK,
		String caseType) {
}
