package com.dylan.esquery.service;

import com.dylan.esquery.api.model.RebuildTask;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

/** 生成本地文档索引验证结果，供 alias 切换门禁比对。 */
@Service
public class DocumentIndexValidationService {

	private static final String VALIDATION_VERSION = "LOCAL_DOCUMENT_INDEX_VALIDATION_V1";

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
		String digest = digest(task);
		taskRepository.markValidationPassed(taskId, digest, VALIDATION_VERSION);
	}

	private boolean isDocumentTask(RebuildTask task) {
		return documentIndexPolicy.isDocumentIndex(task.getIndex())
				|| documentIndexPolicy.isDocumentIndex(task.getTargetIndex());
	}

	private static String digest(RebuildTask task) {
		String content = String.join("|",
				VALIDATION_VERSION,
				value(task.getTaskId()),
				value(task.getIndex()),
				value(task.getTargetIndex()),
				value(task.getType()),
				value(task.getStatus()),
				String.valueOf(task.getTotalIndexed()),
				value(task.getLastCursor()));
		try {
			MessageDigest digest = MessageDigest.getInstance("SHA-256");
			return HexFormat.of().formatHex(digest.digest(content.getBytes(StandardCharsets.UTF_8)));
		} catch (NoSuchAlgorithmException ex) {
			throw new IllegalStateException("SHA-256 not available", ex);
		}
	}

	private static String value(String value) {
		return value == null ? "" : value;
	}
}
