package com.dylan.agent.employee.application;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jwt.Jwt;

import com.dylan.agent.employee.api.AgentBusinessException;
import com.dylan.agent.employee.api.model.AgentEmployeeField;
import com.dylan.agent.employee.api.model.AgentEmployeeQueryRequest;
import com.dylan.agent.employee.api.model.AgentPageRequest;
import com.dylan.agent.employee.client.EmployeeSearchClient;
import com.dylan.agent.employee.mapping.EmployeeSearchRequestMapper;
import com.dylan.agent.employee.mapping.EmployeeSearchResponseMapper;
import com.dylan.agent.employee.security.AgentEmployeeDelegatedAuthorization;

class AgentEmployeeQueryServiceTest {

	@Test
	void invalidPlanNeverReachesAuthorizationOrEmployeeService() {
		AgentEmployeeDelegatedAuthorization authorization = mock(AgentEmployeeDelegatedAuthorization.class);
		EmployeeSearchClient client = mock(EmployeeSearchClient.class);
		EmployeeSearchResponseMapper responseMapper = mock(EmployeeSearchResponseMapper.class);
		Clock clock = Clock.fixed(Instant.parse("2026-07-23T12:00:00Z"), ZoneOffset.UTC);
		AgentEmployeeQueryService service = new AgentEmployeeQueryService(
				authorization, new EmployeeSearchRequestMapper(), client, responseMapper, clock);
		AgentEmployeeQueryRequest request = new AgentEmployeeQueryRequest(
				"00000000-0000-0000-0000-000000000001",
				List.of(), List.of(AgentEmployeeField.POSITION, AgentEmployeeField.POSITION),
				List.of(), new AgentPageRequest(0, 10), Instant.parse("2026-07-23T12:00:10Z"));

		assertThatThrownBy(() -> service.query(request, mock(Jwt.class)))
				.isInstanceOfSatisfying(AgentBusinessException.class,
						ex -> org.assertj.core.api.Assertions.assertThat(ex.code())
								.isEqualTo("AGENT_BUSINESS_INVALID_REQUEST"));
		verifyNoInteractions(authorization, client, responseMapper);
	}

	@Test
	void expiredDeadlineNeverReachesAuthorizationOrEmployeeService() {
		AgentEmployeeDelegatedAuthorization authorization = mock(AgentEmployeeDelegatedAuthorization.class);
		EmployeeSearchClient client = mock(EmployeeSearchClient.class);
		EmployeeSearchResponseMapper responseMapper = mock(EmployeeSearchResponseMapper.class);
		Clock clock = Clock.fixed(Instant.parse("2026-07-23T12:00:00Z"), ZoneOffset.UTC);
		AgentEmployeeQueryService service = new AgentEmployeeQueryService(
				authorization, new EmployeeSearchRequestMapper(), client, responseMapper, clock);
		AgentEmployeeQueryRequest request = new AgentEmployeeQueryRequest(
				"00000000-0000-0000-0000-000000000001",
				List.of(), List.of(AgentEmployeeField.POSITION),
				List.of(), new AgentPageRequest(0, 10), Instant.parse("2026-07-23T11:59:59Z"));

		assertThatThrownBy(() -> service.query(request, mock(Jwt.class)))
				.isInstanceOfSatisfying(AgentBusinessException.class,
						ex -> org.assertj.core.api.Assertions.assertThat(ex.code())
								.isEqualTo("AGENT_BUSINESS_INVALID_REQUEST"));
		verifyNoInteractions(authorization, client, responseMapper);
	}
}
