package com.dylan.esquery.service;

import com.dylan.esquery.api.model.RebuildTask;
import org.springframework.stereotype.Service;

/** 生成本地文档索引验证结果，供 alias 切换门禁比对。 */
@Service
public class DocumentIndexValidationService {

	private static final String VALIDATION_VERSION = "LOCAL_DOCUMENT_INDEX_VALIDATION_V2";

	private final DocumentIndexPolicy documentIndexPolicy;
	private final RebuildTaskRepository taskRepository;

	public DocumentIndexValidationService(
			DocumentIndexPolicy documentIndexPolicy,
			RebuildTaskRepository taskRepository) {
		this.documentIndexPolicy = documentIndexPolicy;
		this.taskRepository = taskRepository;
	}

	public void validateSuccessfulTask(String taskId) {
		RebuildTask task = taskRepository.findById(taskId);
		if (!isDocumentTask(task)) {
			taskRepository.markValidationSkipped(taskId, "non-document index rebuild");
			return;
		}
		if (!"SUCCESS".equals(task.getStatus())) {
			taskRepository.markValidationFailed(taskId, "rebuild task is not SUCCESS");
			throw new IllegalStateException("rebuild task must be SUCCESS before validation");
		}
		DocumentIndexValidationReport report = DocumentIndexValidationReport.localPassed(task, VALIDATION_VERSION);
		taskRepository.markValidationPassed(taskId, report.validationDigest(), report.validatorVersion());
	}

	public DocumentIndexValidationReport validateDocumentIndex(DocumentRetrievalValidationRequest request) {
		validateRequest(request);
		RebuildTask task = taskRepository.findById(request.taskId());
		if (!isDocumentTask(task)) {
			taskRepository.markValidationSkipped(request.taskId(), "non-document index rebuild");
			throw new IllegalArgumentException("validation task must be a document index rebuild");
		}
		if (!"SUCCESS".equals(task.getStatus())) {
			taskRepository.markValidationFailed(request.taskId(), "rebuild task is not SUCCESS");
			throw new IllegalStateException("rebuild task must be SUCCESS before validation");
		}
		validateGoldCases(request);
		var failures = DocumentIndexValidationReport.validationFailures(request);
		if (!failures.isEmpty()) {
			taskRepository.markValidationFailed(request.taskId(), String.join(",", failures));
			throw new IllegalStateException("document retrieval validation failed: " + String.join(",", failures));
		}
		DocumentIndexValidationReport report = DocumentIndexValidationReport.passed(task, VALIDATION_VERSION, request);
		taskRepository.markValidationPassed(request.taskId(), report.validationDigest(), report.validatorVersion());
		return report;
	}

	private void validateRequest(DocumentRetrievalValidationRequest request) {
		if (request == null) {
			throw new IllegalArgumentException("validation request must not be null");
		}
		requireNonBlank(request.taskId(), "taskId");
		requireNonBlank(request.domain(), "domain");
		requireNonBlank(request.materialType(), "materialType");
		requireNonBlank(request.retrievalProfile(), "retrievalProfile");
		requireNonBlank(request.profileVersion(), "profileVersion");
		requireNonBlank(request.indexAlias(), "indexAlias");
		requireNonBlank(request.indexVersion(), "indexVersion");
		requireNonBlank(request.goldSetVersion(), "goldSetVersion");
		if (!documentIndexPolicy.isDocumentIndex(request.indexAlias())) {
			throw new IllegalArgumentException("indexAlias must be a document alias");
		}
		if (request.minimumTopKHitRate() < 0.0d || request.minimumTopKHitRate() > 1.0d
				|| request.actualTopKHitRate() < 0.0d || request.actualTopKHitRate() > 1.0d) {
			throw new IllegalArgumentException("gold query hit rate must be between 0 and 1");
		}
		if (request.permissionLeakCount() < 0) {
			throw new IllegalArgumentException("permissionLeakCount must not be negative");
		}
	}

	private void validateGoldCases(DocumentRetrievalValidationRequest request) {
		var cases = request.goldQueryCases();
		if (cases == null || cases.isEmpty()) {
			throw new IllegalArgumentException("gold query cases must not be empty");
		}
		for (DocumentGoldQueryCase goldCase : cases) {
			if (goldCase == null) {
				throw new IllegalArgumentException("gold query case must not be null");
			}
			requireNonBlank(goldCase.caseId(), "gold case caseId");
			requireNonBlank(goldCase.query(), "gold case query");
			if (!request.domain().equals(goldCase.domain())
					|| !request.materialType().equals(goldCase.materialType())
					|| !request.retrievalProfile().equals(goldCase.retrievalProfile())
					|| !request.profileVersion().equals(goldCase.profileVersion())
					|| !request.goldSetVersion().equals(goldCase.goldSetVersion())) {
				throw new IllegalArgumentException("gold query case scope does not match validation request");
			}
			if ((goldCase.expectedDocumentIds() == null || goldCase.expectedDocumentIds().isEmpty())
					&& (goldCase.deniedDocumentIds() == null || goldCase.deniedDocumentIds().isEmpty())
					&& (goldCase.revokedDocumentIds() == null || goldCase.revokedDocumentIds().isEmpty())) {
				throw new IllegalArgumentException("gold query case must define expected, denied or revoked documents");
			}
		}
	}

	private static void requireNonBlank(String value, String name) {
		if (value == null || value.isBlank()) {
			throw new IllegalArgumentException(name + " must not be blank");
		}
	}

	private boolean isDocumentTask(RebuildTask task) {
		return documentIndexPolicy.isDocumentIndex(task.getIndex())
				|| documentIndexPolicy.isDocumentIndex(task.getTargetIndex());
	}

}
