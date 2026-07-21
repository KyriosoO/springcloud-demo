package com.dylan.esquery.service;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Executor;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import com.dylan.esquery.api.model.RebuildRequest;
import com.dylan.esquery.api.model.RebuildTask;
import com.dylan.esquery.api.model.SourcePageResponse;
import com.dylan.esquery.config.EsQueryProperties;

/**
 * 索引重建服务，负责编排全量索引重建任务。
 */
@Service
public class IndexRebuildService {
	private static final int DEFAULT_BATCH_SIZE = 500;

	private final EsDocumentService esDocumentService;
	private final RebuildTaskRepository taskRepository;
	private final DocumentIndexPolicy documentIndexPolicy;
	private final DocumentSourceUrlPolicy sourceUrlPolicy;
	private final EsQueryProperties properties;
	private final RestTemplate restTemplate;
	private final Executor rebuildExecutor;

	/**
	 * 创建 IndexRebuildService 实例并注入所需依赖。
	 */
	@Autowired
	public IndexRebuildService(EsDocumentService esDocumentService, RebuildTaskRepository taskRepository,
			DocumentIndexPolicy documentIndexPolicy,
			DocumentSourceUrlPolicy sourceUrlPolicy,
			EsQueryProperties properties,
			@Qualifier("esRebuildExecutor") Executor rebuildExecutor) {
		this(esDocumentService, taskRepository, documentIndexPolicy,
				sourceUrlPolicy, properties, new RestTemplate(), rebuildExecutor);
	}

	IndexRebuildService(EsDocumentService esDocumentService, RebuildTaskRepository taskRepository,
			DocumentIndexPolicy documentIndexPolicy,
			DocumentSourceUrlPolicy sourceUrlPolicy,
			EsQueryProperties properties,
			RestTemplate restTemplate,
			Executor rebuildExecutor) {
		this.esDocumentService = esDocumentService;
		this.taskRepository = taskRepository;
		this.documentIndexPolicy = documentIndexPolicy;
		this.sourceUrlPolicy = sourceUrlPolicy;
		this.properties = properties;
		this.restTemplate = restTemplate;
		this.rebuildExecutor = rebuildExecutor;
	}

	public IndexRebuildService(EsDocumentService esDocumentService, RebuildTaskRepository taskRepository,
			DocumentIndexPolicy documentIndexPolicy,
			@Qualifier("esRebuildExecutor") Executor rebuildExecutor) {
		this(esDocumentService, taskRepository, documentIndexPolicy,
				new DocumentSourceUrlPolicy(defaultProperties()), defaultProperties(), new RestTemplate(), rebuildExecutor);
	}

	public IndexRebuildService(EsDocumentService esDocumentService, RebuildTaskRepository taskRepository,
			@Qualifier("esRebuildExecutor") Executor rebuildExecutor) {
		this(esDocumentService, taskRepository, new DocumentIndexPolicy(defaultProperties()), rebuildExecutor);
	}

	/**
	 * 处理 submitFullRebuild 相关逻辑。
	 */
	public synchronized RebuildTask submitFullRebuild(String index, RebuildRequest request) {
		validateRequest(index, request, true);
		String targetIndex = targetIndex(index, request);
		String taskId = UUID.randomUUID().toString();
		RebuildTask task = taskRepository.create(taskId, index, targetIndex, "FULL");
		rebuildExecutor.execute(() -> runFullRebuild(taskId, request));
		return task;
	}

	/**
	 * 处理 submitIncrementalRebuild 相关逻辑。
	 */
	public synchronized RebuildTask submitIncrementalRebuild(String index, RebuildRequest request) {
		validateRequest(index, request, false);
		String targetIndex = targetIndex(index, request);
		String taskId = UUID.randomUUID().toString();
		RebuildTask task = taskRepository.create(taskId, index, targetIndex, "INCREMENTAL");
		rebuildExecutor.execute(() -> runIncrementalRebuild(taskId, request));
		return task;
	}

	/**
	 * 处理 runFullRebuild 相关逻辑。
	 */
	private void runFullRebuild(String taskId, RebuildRequest request) {
		RebuildTask task = taskRepository.findById(taskId);
		try {
			taskRepository.markRunning(taskId);
			esDocumentService.recreateIndex(task.getTargetIndex(), request.getIndexDefinition());
			pullAndIndex(taskId, request);
			taskRepository.markSuccess(taskId);
		} catch (Exception e) {
			taskRepository.markFailed(taskId, e);
		}
	}

	/**
	 * 处理 runIncrementalRebuild 相关逻辑。
	 */
	private void runIncrementalRebuild(String taskId, RebuildRequest request) {
		try {
			taskRepository.markRunning(taskId);
			pullAndIndex(taskId, request);
			taskRepository.markSuccess(taskId);
		} catch (Exception e) {
			taskRepository.markFailed(taskId, e);
		}
	}

	/**
	 * 处理 pullAndIndex 相关逻辑。
	 */
	private void pullAndIndex(String taskId, RebuildRequest request) throws Exception {
		RebuildTask task = taskRepository.findById(taskId);
		String cursor = request.getCursor();
		long total = 0;
		boolean hasMore;
		do {
			SourcePageResponse page = fetchPage(request, cursor);
			validateSourcePage(page);
			List<Map<String, Object>> documents = page.getDocuments();
			if (documents != null && !documents.isEmpty()) {
				esDocumentService.bulkIndex(task.getTargetIndex(), request.getIdField(), documents);
				total += documents.size();
			}
			cursor = page.getNextCursor();
			hasMore = page.isHasMore();
			taskRepository.markProgress(taskId, total, cursor);
		} while (hasMore);
	}

	/**
	 * 处理 fetchPage 相关逻辑。
	 */
	private SourcePageResponse fetchPage(RebuildRequest request, String cursor) {
		UriComponentsBuilder builder = UriComponentsBuilder.fromUriString(request.getSourceUrl())
				.queryParam("batchSize", batchSize(request));
		if (cursor != null && !cursor.isBlank()) {
			builder.queryParam("cursor", cursor);
		}
		if (request.getSince() != null && !request.getSince().isBlank()) {
			builder.queryParam("since", request.getSince());
		}
		if (request.getSourceParams() != null) {
			for (Map.Entry<String, Object> entry : request.getSourceParams().entrySet()) {
				if (entry.getKey() != null && entry.getValue() != null) {
					builder.queryParam(entry.getKey(), entry.getValue());
				}
			}
		}
		return restTemplate.getForObject(builder.toUriString(), SourcePageResponse.class);
	}

	/**
	 * 校验相关业务规则。
	 */
	private void validateRequest(String index, RebuildRequest request, boolean fullRebuild) {
		if (request == null || request.getSourceUrl() == null || request.getSourceUrl().isBlank()) {
			throw new IllegalArgumentException("sourceUrl must not be blank");
		}
		sourceUrlPolicy.validate(request.getSourceUrl());
		if (request.getBatchSize() != null && request.getBatchSize() <= 0) {
			throw new IllegalArgumentException("batchSize must be greater than 0");
		}
		if (batchSize(request) > properties.getRebuildMaxBatchSize()) {
			throw new IllegalArgumentException("batchSize must not exceed rebuildMaxBatchSize");
		}
		validateSourceParams(request.getSourceParams());
		String targetIndex = targetIndex(index, request);
		if (documentIndexPolicy.isDocumentIndex(index) || documentIndexPolicy.isDocumentIndex(targetIndex)) {
			throw new IllegalArgumentException("DOCUMENT_SPECIALIZED_ENDPOINT_REQUIRED");
		}
	}

	private void validateSourcePage(SourcePageResponse page) {
		if (page == null) {
			throw new IllegalArgumentException("source page response must not be null");
		}
		List<Map<String, Object>> documents = page.getDocuments();
		if (page.isHasMore() && (documents == null || documents.isEmpty())) {
			throw new IllegalArgumentException("source page must not be empty when hasMore is true");
		}
	}

	private void validateSourceParams(Map<String, Object> sourceParams) {
		if (sourceParams == null || sourceParams.isEmpty()) {
			return;
		}
		for (String reserved : List.of("batchSize", "cursor", "since")) {
			boolean containsReserved = sourceParams.keySet().stream()
					.anyMatch(key -> key != null && reserved.equalsIgnoreCase(key));
			if (containsReserved) {
				throw new IllegalArgumentException("sourceParams must not override reserved parameter: " + reserved);
			}
		}
	}

	/**
	 * 处理 batchSize 相关逻辑。
	 */
	private int batchSize(RebuildRequest request) {
		if (request.getBatchSize() == null || request.getBatchSize() <= 0) {
			return DEFAULT_BATCH_SIZE;
		}
		return request.getBatchSize();
	}

	/**
	 * 处理 targetIndex 相关逻辑。
	 */
	private String targetIndex(String index, RebuildRequest request) {
		if (request != null && request.getTargetIndex() != null && !request.getTargetIndex().isBlank()) {
			return request.getTargetIndex();
		}
		return index;
	}

	private static EsQueryProperties defaultProperties() {
		EsQueryProperties properties = new EsQueryProperties();
		properties.setTotalHitsThreshold(10000);
		properties.setDocumentSourceAllowedHosts(List.of("document-platform"));
		properties.setRebuildMaxBatchSize(DEFAULT_BATCH_SIZE);
		return properties;
	}
}
