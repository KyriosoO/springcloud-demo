package com.dylan.esquery.service;

import java.util.List;
import java.util.Map;

/** ES v2 alias 切换前的文档检索验证请求。 */
public record DocumentRetrievalValidationRequest(
		String taskId,
		String domain,
		String materialType,
		String retrievalProfile,
		String profileVersion,
		String indexAlias,
		String indexVersion,
		String goldSetVersion,
		boolean schemaValidated,
		boolean aclValidated,
		boolean rollbackDryRunReady,
		double minimumTopKHitRate,
		double actualTopKHitRate,
		int permissionLeakCount,
		List<DocumentGoldQueryCase> goldQueryCases,
		Map<String, Double> metrics) {
}
