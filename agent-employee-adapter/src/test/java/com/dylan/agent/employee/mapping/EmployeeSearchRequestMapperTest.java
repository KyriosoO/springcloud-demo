package com.dylan.agent.employee.mapping;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.List;

import org.junit.jupiter.api.Test;

import com.dylan.agent.employee.api.model.AgentEmployeeField;
import com.dylan.agent.employee.api.model.AgentEmployeeFilter;
import com.dylan.agent.employee.api.model.AgentEmployeeQueryRequest;
import com.dylan.agent.employee.api.model.AgentEmployeeSort;
import com.dylan.agent.employee.api.model.AgentPageRequest;
import com.dylan.agent.employee.api.model.AgentQueryOperator;
import com.dylan.agent.employee.api.model.AgentSortDirection;
import com.dylan.agent.employee.client.EmployeeSearchRequest;

class EmployeeSearchRequestMapperTest {

	@Test
	void mapsBoundedAgentContractToExistingEmployeeSearchContract() {
		AgentEmployeeQueryRequest request = new AgentEmployeeQueryRequest(
				"00000000-0000-0000-0000-000000000001",
				List.of(
						new AgentEmployeeFilter(AgentEmployeeField.POSITION, AgentQueryOperator.EQ, List.of("Engineer")),
						new AgentEmployeeFilter(AgentEmployeeField.WORK_BASE_SI, AgentQueryOperator.IN,
								List.of("SHANGHAI", "BEIJING"))),
				List.of(AgentEmployeeField.POSITION, AgentEmployeeField.WORK_BASE_SI),
				List.of(new AgentEmployeeSort(AgentEmployeeField.POSITION, AgentSortDirection.DESC)),
				new AgentPageRequest(2, 25),
				Instant.parse("2026-07-24T00:00:00Z"));

		EmployeeSearchRequest mapped = new EmployeeSearchRequestMapper().map(request);

		assertThat(mapped.from()).isEqualTo(50);
		assertThat(mapped.size()).isEqualTo(25);
		assertThat(mapped.filters()).containsExactly(
				new EmployeeSearchRequest.EmployeeSearchFilter("position", "eq", "Engineer", List.of()),
				new EmployeeSearchRequest.EmployeeSearchFilter(
						"workBaseSi", "in", null, List.of("SHANGHAI", "BEIJING")));
		assertThat(mapped.sorts()).containsExactly(
				new EmployeeSearchRequest.EmployeeSearchSort("position", "DESC"));
	}
}
