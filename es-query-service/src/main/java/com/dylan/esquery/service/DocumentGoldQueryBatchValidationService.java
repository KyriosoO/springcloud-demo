package com.dylan.esquery.service;

import com.dylan.esquery.api.model.HybridSearchChannelRequest;
import com.dylan.esquery.api.model.HybridSearchRequest;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** 批跑真实 ES gold query，并生成 alias 切换前的检索验证报告。 */
@Service
public class DocumentGoldQueryBatchValidationService {

	private static final int DEFAULT_TOP_K = 10;
	private static final int DEFAULT_RRF_K = 60;
	private static final int DEFAULT_CHANNEL_K = 20;

	private final DocumentGoldQuerySearchExecutor searchExecutor;
	private final DocumentIndexValidationService validationService;
	private final EsIndexAliasService aliasService;

	public DocumentGoldQueryBatchValidationService(
			DocumentGoldQuerySearchExecutor searchExecutor,
			DocumentIndexValidationService validationService,
			EsIndexAliasService aliasService) {
		this.searchExecutor = searchExecutor;
		this.validationService = validationService;
		this.aliasService = aliasService;
	}

	public DocumentIndexValidationReport validate(DocumentGoldQueryBatchValidationRequest request) throws IOException {
		return validationService.validateDocumentIndex(buildValidationRequest(request));
	}

	DocumentRetrievalValidationRequest buildValidationRequest(DocumentGoldQueryBatchValidationRequest request)
			throws IOException {
		validateRequest(request);
		int expectedCaseCount = 0;
		int expectedHitCount = 0;
		int aclProbeCount = 0;
		Set<String> leakedPairs = new LinkedHashSet<>();
		for (DocumentGoldQueryCase goldCase : request.goldQueryCases()) {
			List<String> documentIds = searchExecutor.searchDocumentIds(
					request.indexAlias(),
					searchRequest(request, goldCase));
			Set<String> hitIds = new LinkedHashSet<>(documentIds);
			if (!empty(goldCase.expectedDocumentIds())) {
				expectedCaseCount++;
				if (goldCase.expectedDocumentIds().stream().anyMatch(hitIds::contains)) {
					expectedHitCount++;
				}
			}
			aclProbeCount += countAclProbes(goldCase);
			recordLeaks(goldCase.caseId(), hitIds, goldCase.deniedDocumentIds(), leakedPairs);
			recordLeaks(goldCase.caseId(), hitIds, goldCase.revokedDocumentIds(), leakedPairs);
		}
		double actualHitRate = expectedCaseCount == 0 ? 0.0d : (double) expectedHitCount / expectedCaseCount;
		boolean rollbackDryRunReady = rollbackDryRunReady(request);
		boolean aclValidated = expectedCaseCount > 0 && aclProbeCount > 0 && leakedPairs.isEmpty();
		Map<String, Double> metrics = new LinkedHashMap<>();
		metrics.put("goldQuery.caseCount", (double) request.goldQueryCases().size());
		metrics.put("goldQuery.expectedCaseCount", (double) expectedCaseCount);
		metrics.put("goldQuery.expectedHitCount", (double) expectedHitCount);
		metrics.put("goldQuery.actualTopKHitRate", actualHitRate);
		metrics.put("acl.probeCount", (double) aclProbeCount);
		metrics.put("acl.permissionLeakCount", (double) leakedPairs.size());
		metrics.put("rollback.dryRunReady", rollbackDryRunReady ? 1.0d : 0.0d);
		return new DocumentRetrievalValidationRequest(
				request.taskId(),
				request.domain(),
				request.materialType(),
				request.retrievalProfile(),
				request.profileVersion(),
				request.indexAlias(),
				request.indexVersion(),
				request.goldSetVersion(),
				request.schemaValidated(),
				aclValidated,
				rollbackDryRunReady,
				request.minimumTopKHitRate(),
				actualHitRate,
				leakedPairs.size(),
				request.goldQueryCases(),
				metrics);
	}

	private boolean rollbackDryRunReady(DocumentGoldQueryBatchValidationRequest request) throws IOException {
		if (request.rollbackRequest() == null) {
			return false;
		}
		return aliasService.rollbackReadAliasDryRun(request.indexAlias(), request.rollbackRequest()).ready();
	}

	private HybridSearchRequest searchRequest(
			DocumentGoldQueryBatchValidationRequest request,
			DocumentGoldQueryCase goldCase) {
		int topK = goldCase.topK() > 0 ? goldCase.topK() : DEFAULT_TOP_K;
		HybridSearchRequest searchRequest = new HybridSearchRequest();
		searchRequest.setQueryText(goldCase.query());
		searchRequest.setDomain(request.domain());
		searchRequest.setMaterialType(request.materialType());
		searchRequest.setRetrievalProfile(request.retrievalProfile());
		searchRequest.setProfileVersion(request.profileVersion());
		searchRequest.setIndexAlias(request.indexAlias());
		searchRequest.setPermissionEvidenceId(request.permissionEvidenceId());
		searchRequest.setPermissionVersion(request.permissionVersion());
		searchRequest.setFilterDigest(request.filterDigest());
		searchRequest.setFilters(request.filters());
		searchRequest.setEmbeddingField(request.embeddingField());
		searchRequest.setChannelWeights(request.channelWeights());
		searchRequest.setTopK(topK);
		searchRequest.setRrfK(DEFAULT_RRF_K);
		searchRequest.setMaxChunksPerDocument(1);
		searchRequest.setSourceExcludes(List.of("embedding"));
		searchRequest.setChannels(channels(goldCase, topK, request.embeddingField()));
		return searchRequest;
	}

	private List<HybridSearchChannelRequest> channels(
			DocumentGoldQueryCase goldCase,
			int topK,
			String embeddingField) {
		List<HybridSearchChannelRequest> channels = new ArrayList<>();
		channels.add(channel("BM25", bm25Dsl(goldCase.query()), null, null, topK));
		channels.add(channel("EXACT", exactDsl(goldCase.query()), null, null, topK));
		channels.add(channel("PHRASE", phraseDsl(goldCase.query()), null, null, topK));
		if (!empty(goldCase.queryVector())) {
			channels.add(channel("DENSE_VECTOR", null, goldCase.queryVector(), embeddingField, topK));
		}
		return channels;
	}

	private HybridSearchChannelRequest channel(
			String name,
			Map<String, Object> queryDsl,
			List<Double> queryVector,
			String embeddingField,
			int topK) {
		HybridSearchChannelRequest channel = new HybridSearchChannelRequest();
		channel.setChannel(name);
		channel.setQueryDsl(queryDsl);
		channel.setQueryVector(queryVector);
		channel.setEmbeddingField(embeddingField);
		channel.setK(Math.max(topK, DEFAULT_CHANNEL_K));
		channel.setNumCandidates(Math.max(topK * 10, 100));
		return channel;
	}

	private Map<String, Object> bm25Dsl(String query) {
		return Map.of("query", Map.of("multi_match", Map.of(
				"query", query,
				"fields", List.of("title^3", "content", "snippet", "section^1.5",
						"documentNo^5", "issuer^2", "taxType^2"))));
	}

	private Map<String, Object> exactDsl(String query) {
		Map<String, Object> bool = new LinkedHashMap<>();
		bool.put("should", List.of(
				term("documentNo", query, "EXACT:documentNo"),
				term("documentNo.keyword", query, "EXACT:documentNo.keyword"),
				term("title.keyword", query, "EXACT:title.keyword"),
				term("issuer", query, "EXACT:issuer"),
				term("issuer.keyword", query, "EXACT:issuer.keyword"),
				term("taxType", query, "EXACT:taxType"),
				term("taxType.keyword", query, "EXACT:taxType.keyword")));
		bool.put("minimum_should_match", 1);
		return Map.of("query", Map.of("bool", bool));
	}

	private Map<String, Object> phraseDsl(String query) {
		return Map.of("query", Map.of("multi_match", Map.of(
				"query", query,
				"type", "phrase",
				"fields", List.of("title^3", "content", "snippet", "section^1.5"))));
	}

	private Map<String, Object> term(String field, String query, String name) {
		return Map.of("term", Map.of(field, Map.of("value", query, "_name", name)));
	}

	private int countAclProbes(DocumentGoldQueryCase goldCase) {
		return size(goldCase.deniedDocumentIds()) + size(goldCase.revokedDocumentIds());
	}

	private void recordLeaks(
			String caseId,
			Set<String> hitIds,
			List<String> protectedIds,
			Set<String> leakedPairs) {
		if (empty(protectedIds)) {
			return;
		}
		for (String documentId : protectedIds) {
			if (documentId != null && hitIds.contains(documentId)) {
				leakedPairs.add(caseId + "|" + documentId);
			}
		}
	}

	private void validateRequest(DocumentGoldQueryBatchValidationRequest request) {
		if (request == null) {
			throw new IllegalArgumentException("gold query batch request must not be null");
		}
		requireNonBlank(request.taskId(), "taskId");
		requireNonBlank(request.domain(), "domain");
		requireNonBlank(request.materialType(), "materialType");
		requireNonBlank(request.retrievalProfile(), "retrievalProfile");
		requireNonBlank(request.profileVersion(), "profileVersion");
		requireNonBlank(request.indexAlias(), "indexAlias");
		requireNonBlank(request.indexVersion(), "indexVersion");
		requireNonBlank(request.goldSetVersion(), "goldSetVersion");
		if (request.filters() == null || request.filters().isEmpty()) {
			throw new IllegalArgumentException("gold query batch requires ACL filters");
		}
		if (request.goldQueryCases() == null || request.goldQueryCases().isEmpty()) {
			throw new IllegalArgumentException("gold query cases must not be empty");
		}
		if (request.minimumTopKHitRate() < 0.0d || request.minimumTopKHitRate() > 1.0d) {
			throw new IllegalArgumentException("minimumTopKHitRate must be between 0 and 1");
		}
	}

	private static void requireNonBlank(String value, String name) {
		if (value == null || value.isBlank()) {
			throw new IllegalArgumentException(name + " must not be blank");
		}
	}

	private static int size(List<?> values) {
		return values == null ? 0 : values.size();
	}

	private static boolean empty(List<?> values) {
		return values == null || values.isEmpty();
	}
}
