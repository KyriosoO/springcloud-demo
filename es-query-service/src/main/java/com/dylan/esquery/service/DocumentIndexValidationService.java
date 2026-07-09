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

	private boolean isDocumentTask(RebuildTask task) {
		return documentIndexPolicy.isDocumentIndex(task.getIndex())
				|| documentIndexPolicy.isDocumentIndex(task.getTargetIndex());
	}

}
