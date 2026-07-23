package com.dylan.agent.employee.application;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.HashSet;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;

import com.dylan.agent.employee.api.AgentBusinessException;
import com.dylan.agent.employee.api.model.AgentEmployeeField;
import com.dylan.agent.employee.api.model.AgentEmployeeFilter;
import com.dylan.agent.employee.api.model.AgentEmployeeQueryRequest;
import com.dylan.agent.employee.api.model.AgentEmployeeQueryResponse;
import com.dylan.agent.employee.api.model.AgentQueryOperator;
import com.dylan.agent.employee.client.EmployeeSearchClient;
import com.dylan.agent.employee.mapping.EmployeeSearchRequestMapper;
import com.dylan.agent.employee.mapping.EmployeeSearchResponseMapper;
import com.dylan.agent.employee.security.AgentEmployeeDelegatedAuthorization;

@Service
public class AgentEmployeeQueryService {

	private final AgentEmployeeDelegatedAuthorization authorization;
	private final EmployeeSearchRequestMapper requestMapper;
	private final EmployeeSearchClient client;
	private final EmployeeSearchResponseMapper responseMapper;
	private final Clock clock;

	@Autowired
	public AgentEmployeeQueryService(AgentEmployeeDelegatedAuthorization authorization,
			EmployeeSearchRequestMapper requestMapper, EmployeeSearchClient client,
			EmployeeSearchResponseMapper responseMapper) {
		this(authorization, requestMapper, client, responseMapper, Clock.systemUTC());
	}

	AgentEmployeeQueryService(AgentEmployeeDelegatedAuthorization authorization,
			EmployeeSearchRequestMapper requestMapper, EmployeeSearchClient client,
			EmployeeSearchResponseMapper responseMapper, Clock clock) {
		this.authorization = authorization;
		this.requestMapper = requestMapper;
		this.client = client;
		this.responseMapper = responseMapper;
		this.clock = clock;
	}

	public AgentEmployeeQueryResponse query(AgentEmployeeQueryRequest request, Jwt jwt) {
		validate(request);
		authorization.verify(jwt, request);
		Duration remaining = Duration.between(Instant.now(clock), request.deadlineAt());
		if (remaining.isZero() || remaining.isNegative()) {
			throw new AgentBusinessException(
					"AGENT_BUSINESS_DEADLINE_EXCEEDED", HttpStatus.REQUEST_TIMEOUT, request.requestId());
		}
		String rawResponse;
		try {
			rawResponse = client.search(requestMapper.map(request), remaining);
		} catch (AgentBusinessException ex) {
			throw new AgentBusinessException(ex.code(), ex.status(), request.requestId());
		}
		if (!request.deadlineAt().isAfter(Instant.now(clock))) {
			throw new AgentBusinessException(
					"AGENT_BUSINESS_DEADLINE_EXCEEDED", HttpStatus.REQUEST_TIMEOUT, request.requestId());
		}
		return responseMapper.map(request, rawResponse);
	}

	private void validate(AgentEmployeeQueryRequest request) {
		if (request == null || request.requestId() == null || request.requestId().isBlank()
				|| request.deadlineAt() == null || !request.deadlineAt().isAfter(Instant.now(clock))
				|| request.page() == null || request.page().number() < 0 || request.page().number() > 100
				|| request.page().size() < 1 || request.page().size() > 100
				|| request.filters().size() > 10 || request.sorts().size() > 2
				|| request.select().isEmpty() || request.select().size() > 2) {
			throw invalid(request);
		}
		for (AgentEmployeeFilter filter : request.filters()) {
			if (filter == null || filter.field() == null || filter.operator() == null
					|| filter.values().isEmpty() || filter.values().stream()
							.anyMatch(value -> value == null || value.isBlank() || value.length() > 200)
					|| (filter.operator() == AgentQueryOperator.EQ && filter.values().size() != 1)
					|| (filter.operator() == AgentQueryOperator.IN && filter.values().size() > 50)) {
				throw invalid(request);
			}
		}
		if (new HashSet<>(request.select()).size() != request.select().size()
				|| request.sorts().stream().anyMatch(sort -> sort == null
						|| sort.field() != AgentEmployeeField.POSITION || sort.direction() == null)) {
			throw invalid(request);
		}
	}

	private static AgentBusinessException invalid(AgentEmployeeQueryRequest request) {
		return new AgentBusinessException("AGENT_BUSINESS_INVALID_REQUEST", HttpStatus.BAD_REQUEST,
				request == null ? "" : request.requestId());
	}
}
