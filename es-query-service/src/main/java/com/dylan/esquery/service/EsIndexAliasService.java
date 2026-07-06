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
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** 受控切换和回滚文档读取 alias。 */
@Service
public class EsIndexAliasService {

	private final RestClient restClient;
	private final ObjectMapper objectMapper;
	private final DocumentIndexPolicy documentIndexPolicy;
	private final RebuildTaskRepository taskRepository;

	public EsIndexAliasService(
			RestClient restClient,
			ObjectMapper objectMapper,
			DocumentIndexPolicy documentIndexPolicy,
			RebuildTaskRepository taskRepository) {
		this.restClient = restClient;
		this.objectMapper = objectMapper;
		this.documentIndexPolicy = documentIndexPolicy;
		this.taskRepository = taskRepository;
	}

	public void switchReadAlias(String alias, AliasSwitchRequest request) throws IOException {
		validateRequest(alias, request);
		assertValidatedTask(request);
		switchAlias(alias, request.getTargetIndex(), request.getExpectedPreviousIndex());
	}

	public void rollbackReadAlias(String alias, AliasSwitchRequest request) throws IOException {
		validateRequest(alias, request);
		assertValidatedTask(request);
		switchAlias(alias, request.getTargetIndex(), request.getExpectedPreviousIndex());
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
		if (!documentIndexPolicy.isDocumentIndex(request.getTargetIndex())) {
			throw new IllegalArgumentException("targetIndex must be a document index");
		}
		if (!documentIndexPolicy.isDocumentIndex(request.getExpectedPreviousIndex())) {
			throw new IllegalArgumentException("expectedPreviousIndex must be a document index");
		}
	}

	private void switchAlias(String alias, String targetIndex, String expectedPreviousIndex) throws IOException {
		if (!targetIndex.equals(alias) && targetIndex.equals(expectedPreviousIndex)) {
			throw new IllegalArgumentException("targetIndex must differ from expectedPreviousIndex");
		}
		List<String> currentIndexes = currentIndexes(alias);
		if (currentIndexes.isEmpty() || !currentIndexes.contains(expectedPreviousIndex)) {
			throw new IllegalArgumentException("current alias target does not match expectedPreviousIndex");
		}
		Request request = new Request("POST", "/_aliases");
		request.setEntity(jsonEntity(objectMapper.writeValueAsString(aliasActions(alias, targetIndex, currentIndexes))));
		restClient.performRequest(request);
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
