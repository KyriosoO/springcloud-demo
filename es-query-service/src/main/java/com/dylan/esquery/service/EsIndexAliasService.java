package com.dylan.esquery.service;

import com.dylan.esquery.api.model.AliasSwitchRequest;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.http.HttpEntity;
import org.apache.http.entity.ContentType;
import org.apache.http.nio.entity.NStringEntity;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.ResponseException;
import org.elasticsearch.client.RestClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.ArrayList;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;

/** 受控切换和回滚文档读取 alias。 */
@Service
public class EsIndexAliasService {

	private final RestClient restClient;
	private final ObjectMapper objectMapper;
	private final DocumentIndexPolicy documentIndexPolicy;
	private final RebuildTaskRepository taskRepository;
	private final AliasOperationAuditRepository auditRepository;

	@Autowired
	public EsIndexAliasService(
			RestClient restClient,
			ObjectMapper objectMapper,
			DocumentIndexPolicy documentIndexPolicy,
			RebuildTaskRepository taskRepository,
			AliasOperationAuditRepository auditRepository) {
		this.restClient = restClient;
		this.objectMapper = objectMapper;
		this.documentIndexPolicy = documentIndexPolicy;
		this.taskRepository = taskRepository;
		this.auditRepository = auditRepository;
	}

	public EsIndexAliasService(
			RestClient restClient,
			ObjectMapper objectMapper,
			DocumentIndexPolicy documentIndexPolicy,
			RebuildTaskRepository taskRepository) {
		this(restClient, objectMapper, documentIndexPolicy, taskRepository, new InMemoryAliasOperationAuditRepository());
	}

	public void switchReadAlias(String alias, AliasSwitchRequest request) throws IOException {
		executeAliasOperation(alias, request, "SWITCH", false);
	}

	public void rollbackReadAlias(String alias, AliasSwitchRequest request) throws IOException {
		executeAliasOperation(alias, request, "ROLLBACK", true);
	}

	public AliasRollbackDryRunResult rollbackReadAliasDryRun(String alias, AliasSwitchRequest request) throws IOException {
		long startedAt = System.nanoTime();
		List<String> currentIndexes = List.of();
		try {
			validateRequest(alias, request);
			assertValidatedTask(request);
			assertTrustedRollbackTarget(alias, request.getTargetIndex());
			currentIndexes = currentIndexes(alias);
			assertAliasTargetReady(request.getTargetIndex(), request.getExpectedPreviousIndex(), currentIndexes);
			recordAliasOperation(alias, "ROLLBACK_DRY_RUN", currentIndexes, request, "READY", null, startedAt);
			return new AliasRollbackDryRunResult(
					alias,
					List.copyOf(currentIndexes),
					request.getTargetIndex(),
					request.getExpectedPreviousIndex(),
					true);
		} catch (RuntimeException | IOException ex) {
			recordAliasOperation(alias, "ROLLBACK_DRY_RUN", currentIndexes, request,
					"FAILED", ex.getClass().getSimpleName(), startedAt);
			throw ex;
		}
	}

	List<AliasOperationAudit> aliasAudits() {
		return auditRepository.findAll();
	}

	List<AliasOperationAudit> aliasHistory() {
		return auditRepository.findAll().stream()
				.filter(audit -> "SUCCESS".equals(audit.result()) || "IDEMPOTENT".equals(audit.result()))
				.toList();
	}

	private void executeAliasOperation(
			String alias,
			AliasSwitchRequest request,
			String operation,
			boolean requireHistory) throws IOException {
		long startedAt = System.nanoTime();
		List<String> fromIndexes = List.of();
		try {
			validateRequest(alias, request);
			assertValidatedTask(request);
			if (requireHistory) {
				assertTrustedRollbackTarget(alias, request.getTargetIndex());
			}
			fromIndexes = switchAlias(alias, request.getTargetIndex(), request.getExpectedPreviousIndex());
			String result = fromIndexes.size() == 1 && fromIndexes.contains(request.getTargetIndex())
					? "IDEMPOTENT"
					: "SUCCESS";
			recordAliasOperation(alias, operation, fromIndexes, request, result, null, startedAt);
		} catch (RuntimeException | IOException ex) {
			recordAliasOperation(alias, operation, fromIndexes, request, "FAILED", ex.getClass().getSimpleName(), startedAt);
			throw ex;
		}
	}

	private void assertTrustedRollbackTarget(String alias, String targetIndex) {
		if (!auditRepository.hasTrustedTarget(alias, targetIndex)) {
			throw new IllegalArgumentException("rollback target is not in trusted alias history");
		}
	}

	private void recordAliasOperation(
			String alias,
			String operation,
			List<String> fromIndexes,
			AliasSwitchRequest request,
			String result,
			String failureReason,
			long startedAt) {
		AliasOperationAudit audit = new AliasOperationAudit(
				alias,
				operation,
				fromIndexes == null ? List.of() : List.copyOf(fromIndexes),
				request == null ? null : request.getTargetIndex(),
				normalize(request == null ? null : request.getDomain()),
				normalize(request == null ? null : request.getMaterialType()),
				normalize(request == null ? null : request.getProfileVersion()),
				normalize(request == null ? null : request.getIndexVersion()),
				normalize(request == null ? null : request.getGoldSetVersion()),
				prefix(request == null ? null : request.getValidationReportId()),
				prefix(request == null ? null : request.getTaskId()),
				prefix(request == null ? null : request.getValidationDigest()),
				hashPrefix(request == null ? null : request.getOperatorRef()),
				result,
				failureReason,
				(System.nanoTime() - startedAt) / 1_000_000,
				Instant.now());
		auditRepository.record(audit);
	}

	private static String normalize(String value) {
		if (value == null || value.isBlank()) {
			return "";
		}
		return value.trim();
	}

	private static String prefix(String value) {
		if (value == null || value.isBlank()) {
			return "";
		}
		String normalized = value.trim();
		return normalized.length() <= 12 ? normalized : normalized.substring(0, 12);
	}

	private static String hashPrefix(String value) {
		if (value == null || value.isBlank()) {
			return "";
		}
		try {
			MessageDigest digest = MessageDigest.getInstance("SHA-256");
			String hash = HexFormat.of().formatHex(digest.digest(value.trim().getBytes(StandardCharsets.UTF_8)));
			return hash.substring(0, 12);
		} catch (NoSuchAlgorithmException ex) {
			throw new IllegalStateException("SHA-256 not available", ex);
		}
	}

	private void validateRequest(String alias, AliasSwitchRequest request) {
		if (!documentIndexPolicy.isDocumentIndex(alias)) {
			throw new IllegalArgumentException("alias switch is only allowed for document indexes");
		}
		if (request == null) {
			throw new IllegalArgumentException("alias switch request must not be null");
		}
		requireNonBlank(request.getTaskId(), "taskId");
		requireNonBlank(request.getTargetIndex(), "targetIndex");
		requireNonBlank(request.getExpectedPreviousIndex(), "expectedPreviousIndex");
		requireNonBlank(request.getValidationDigest(), "validationDigest");
		requireNonBlank(request.getOperatorRef(), "operatorRef");
		requireNonBlank(request.getDomain(), "domain");
		requireNonBlank(request.getMaterialType(), "materialType");
		requireNonBlank(request.getProfileVersion(), "profileVersion");
		requireNonBlank(request.getIndexVersion(), "indexVersion");
		requireNonBlank(request.getGoldSetVersion(), "goldSetVersion");
		requireNonBlank(request.getValidationReportId(), "validationReportId");
		if (!documentIndexPolicy.isDocumentIndex(request.getTargetIndex())) {
			throw new IllegalArgumentException("targetIndex must be a document index");
		}
		if (!documentIndexPolicy.isDocumentIndex(request.getExpectedPreviousIndex())) {
			throw new IllegalArgumentException("expectedPreviousIndex must be a document index");
		}
	}

	private void assertValidatedTask(AliasSwitchRequest request) {
		var task = taskRepository.findById(request.getTaskId());
		if (!"SUCCESS".equals(task.getStatus())) {
			throw new IllegalArgumentException("rebuild task must be SUCCESS before switching alias");
		}
		if (!request.getTargetIndex().equals(task.getTargetIndex())) {
			throw new IllegalArgumentException("targetIndex does not match rebuild task");
		}
		if (!"PASSED".equals(task.getValidationStatus())) {
			throw new IllegalArgumentException("rebuild task validation must be PASSED before switching alias");
		}
		if (!request.getValidationDigest().equals(task.getValidationDigest())) {
			throw new IllegalArgumentException("validationDigest does not match rebuild task");
		}
	}

	private List<String> switchAlias(String alias, String targetIndex, String expectedPreviousIndex) throws IOException {
		List<String> currentIndexes = currentIndexes(alias);
		assertAliasTargetReady(targetIndex, expectedPreviousIndex, currentIndexes);
		if (currentIndexes.size() == 1 && currentIndexes.contains(targetIndex)) {
			return currentIndexes;
		}
		Request request = new Request("POST", "/_aliases");
		request.setEntity(jsonEntity(objectMapper.writeValueAsString(aliasActions(alias, targetIndex, currentIndexes))));
		restClient.performRequest(request);
		return currentIndexes;
	}

	private void assertAliasTargetReady(
			String targetIndex,
			String expectedPreviousIndex,
			List<String> currentIndexes) {
		if (!targetIndex.equals(expectedPreviousIndex) && currentIndexes.size() == 1 && currentIndexes.contains(targetIndex)) {
			return;
		}
		if (targetIndex.equals(expectedPreviousIndex)) {
			throw new IllegalArgumentException("targetIndex must differ from expectedPreviousIndex");
		}
		if (currentIndexes.size() == 1 && currentIndexes.contains(targetIndex)) {
			return;
		}
		if (currentIndexes.isEmpty() || !currentIndexes.contains(expectedPreviousIndex)) {
			throw new IllegalArgumentException("current alias target does not match expectedPreviousIndex");
		}
	}

	private Map<String, Object> aliasActions(String alias, String targetIndex, List<String> currentIndexes) {
		List<Object> actions = new ArrayList<>();
		for (String index : currentIndexes) {
			actions.add(Map.of("remove", Map.of("index", index, "alias", alias)));
		}
		actions.add(Map.of("add", Map.of("index", targetIndex, "alias", alias)));
		return Map.of("actions", actions);
	}

	private List<String> currentIndexes(String alias) throws IOException {
		Request request = new Request("GET", "/_alias/" + alias);
		try {
			Response response = restClient.performRequest(request);
			JsonNode root = objectMapper.readTree(response.getEntity().getContent());
			List<String> indexes = new ArrayList<>();
			root.fieldNames().forEachRemaining(indexes::add);
			return indexes;
		} catch (ResponseException ex) {
			if (ex.getResponse().getStatusLine().getStatusCode() == 404) {
				return List.of();
			}
			throw ex;
		}
	}

	private static void requireNonBlank(String value, String name) {
		if (value == null || value.isBlank()) {
			throw new IllegalArgumentException(name + " must not be blank");
		}
	}

	private HttpEntity jsonEntity(String json) {
		return new NStringEntity(json, ContentType.APPLICATION_JSON);
	}
}
