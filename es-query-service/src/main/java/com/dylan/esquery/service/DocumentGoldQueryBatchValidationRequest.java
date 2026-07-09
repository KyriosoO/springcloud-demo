package com.dylan.esquery.service;

import com.dylan.esquery.api.model.AliasSwitchRequest;

import java.util.List;
import java.util.Map;

/** gold query 批跑验证输入，包含检索过滤和回滚 dry-run 请求。 */
public record DocumentGoldQueryBatchValidationRequest(
		String taskId,
		String domain,
		String materialType,
		String retrievalProfile,
		String profileVersion,
		String indexAlias,
		String indexVersion,
		String goldSetVersion,
		boolean schemaValidated,
		double minimumTopKHitRate,
		Map<String, Object> filters,
		String permissionEvidenceId,
		String permissionVersion,
		String filterDigest,
		String embeddingField,
		Map<String, Double> channelWeights,
		AliasSwitchRequest rollbackRequest,
		List<DocumentGoldQueryCase> goldQueryCases) {
}
