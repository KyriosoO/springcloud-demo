package com.dylan.workflow.support;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

import org.springframework.stereotype.Component;

import com.dylan.workflow.model.WorkflowInstance;
import com.dylan.workflow.model.WorkflowNodeInstance;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

@Component
public class WorkflowTodoIdCodec {
	private static final int VERSION = 1;
	private static final String PREFIX = "td1_";

	private final ObjectMapper objectMapper;

	public WorkflowTodoIdCodec(ObjectMapper objectMapper) {
		this.objectMapper = objectMapper;
	}

	public String encode(WorkflowInstance instance, WorkflowNodeInstance node, String operator) {
		WorkflowTodoToken token = new WorkflowTodoToken(VERSION, instance.getProcessId(),
				instance.getCurrentNodeIndex(), node.getNodeId(), operator);
		try {
			byte[] json = objectMapper.writeValueAsBytes(token);
			return PREFIX + Base64.getUrlEncoder().withoutPadding().encodeToString(json);
		} catch (JsonProcessingException e) {
			throw new IllegalStateException("Failed to encode workflow todo id", e);
		}
	}

	public WorkflowTodoToken decode(String todoId) {
		if (todoId == null || !todoId.startsWith(PREFIX)) {
			throw new IllegalArgumentException("Invalid workflow todo id");
		}
		try {
			String encoded = todoId.substring(PREFIX.length());
			byte[] json = Base64.getUrlDecoder().decode(encoded);
			WorkflowTodoToken token = objectMapper.readValue(new String(json, StandardCharsets.UTF_8),
					WorkflowTodoToken.class);
			if (token.version() != VERSION) {
				throw new IllegalArgumentException("Unsupported workflow todo id version");
			}
			return token;
		} catch (IllegalArgumentException e) {
			throw e;
		} catch (Exception e) {
			throw new IllegalArgumentException("Invalid workflow todo id", e);
		}
	}
}
