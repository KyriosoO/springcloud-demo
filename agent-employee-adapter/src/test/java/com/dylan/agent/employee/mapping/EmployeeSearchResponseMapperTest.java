package com.dylan.agent.employee.mapping;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.util.List;

import org.junit.jupiter.api.Test;

import com.dylan.agent.employee.api.AgentBusinessException;
import com.dylan.agent.employee.api.model.AgentEmployeeField;
import com.dylan.agent.employee.api.model.AgentEmployeeQueryRequest;
import com.dylan.agent.employee.api.model.AgentPageRequest;
import com.fasterxml.jackson.databind.ObjectMapper;

class EmployeeSearchResponseMapperTest {

	private final EmployeeSearchResponseMapper mapper = new EmployeeSearchResponseMapper(new ObjectMapper());

	@Test
	void projectsOnlySelectedFieldsAndLeavesUnprovenMetadataNull() {
		AgentEmployeeQueryRequest request = request(List.of(AgentEmployeeField.POSITION));
		String raw = """
				{"hits":{"total":{"value":1,"relation":"eq"},"hits":[{"_source":{
				  "position":"Engineer","workBaseSi":"SHANGHAI","idCardNo":"secret"
				}}]}}
				""";

		var response = mapper.map(request, raw);

		assertThat(response.total()).isEqualTo(1);
		assertThat(response.items()).hasSize(1);
		assertThat(response.items().getFirst().position()).isEqualTo("Engineer");
		assertThat(response.items().getFirst().workBaseSi()).isNull();
		assertThat(response.observedAt()).isNull();
		assertThat(response.sourceVersion()).isNull();
	}

	@Test
	void rejectsUnexpectedSelectedFieldTypeWithoutLeakingRawResponse() {
		AgentEmployeeQueryRequest request = request(List.of(AgentEmployeeField.POSITION));

		assertThatThrownBy(() -> mapper.map(
				request, "{\"hits\":{\"total\":1,\"hits\":[{\"_source\":{\"position\":7}}]}}"))
				.isInstanceOfSatisfying(AgentBusinessException.class, ex -> {
					assertThat(ex.code()).isEqualTo("AGENT_BUSINESS_UNAVAILABLE");
					assertThat(ex.requestId()).isEqualTo(request.requestId());
				});
	}

	private static AgentEmployeeQueryRequest request(List<AgentEmployeeField> select) {
		return new AgentEmployeeQueryRequest(
				"00000000-0000-0000-0000-000000000001",
				List.of(), select, List.of(), new AgentPageRequest(0, 10),
				Instant.parse("2026-07-24T00:00:00Z"));
	}
}
