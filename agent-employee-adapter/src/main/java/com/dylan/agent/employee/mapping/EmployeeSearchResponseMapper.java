package com.dylan.agent.employee.mapping;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

import com.dylan.agent.employee.api.AgentBusinessException;
import com.dylan.agent.employee.api.model.AgentEmployeeField;
import com.dylan.agent.employee.api.model.AgentEmployeeItem;
import com.dylan.agent.employee.api.model.AgentEmployeeQueryRequest;
import com.dylan.agent.employee.api.model.AgentEmployeeQueryResponse;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

@Component
public class EmployeeSearchResponseMapper {

	private final ObjectMapper objectMapper;

	public EmployeeSearchResponseMapper(ObjectMapper objectMapper) {
		this.objectMapper = objectMapper;
	}

	public AgentEmployeeQueryResponse map(AgentEmployeeQueryRequest request, String rawResponse) {
		try {
			JsonNode root = objectMapper.readTree(rawResponse);
			JsonNode hits = root.path("hits");
			JsonNode rows = hits.path("hits");
			if (!hits.isObject() || !rows.isArray()) {
				throw unavailable(request.requestId());
			}
			Set<AgentEmployeeField> selected = new HashSet<>(request.select());
			List<AgentEmployeeItem> items = new ArrayList<>();
			for (JsonNode row : rows) {
				JsonNode source = row.path("_source");
				if (!source.isObject()) {
					throw unavailable(request.requestId());
				}
				items.add(new AgentEmployeeItem(
						selected.contains(AgentEmployeeField.POSITION)
								? nullableText(source, "position", request.requestId()) : null,
						selected.contains(AgentEmployeeField.WORK_BASE_SI)
								? nullableText(source, "workBaseSi", request.requestId()) : null));
			}
			return new AgentEmployeeQueryResponse(
					request.requestId(), List.copyOf(items), request.page(), total(hits.path("total")), null, null);
		} catch (JsonProcessingException ex) {
			throw unavailable(request.requestId());
		}
	}

	private static Long total(JsonNode total) {
		if (total.isIntegralNumber()) {
			return total.longValue();
		}
		JsonNode value = total.path("value");
		return value.isIntegralNumber() ? value.longValue() : null;
	}

	private static String nullableText(JsonNode source, String field, String requestId) {
		JsonNode value = source.get(field);
		if (value == null || value.isNull()) {
			return null;
		}
		if (!value.isTextual()) {
			throw unavailable(requestId);
		}
		return value.textValue();
	}

	private static AgentBusinessException unavailable(String requestId) {
		return new AgentBusinessException(
				"AGENT_BUSINESS_UNAVAILABLE", HttpStatus.SERVICE_UNAVAILABLE, requestId);
	}
}
