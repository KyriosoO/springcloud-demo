package com.dylan.agent.employee.api;

import java.util.UUID;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.dylan.agent.employee.api.model.AgentBusinessErrorResponse;
import com.dylan.agent.employee.api.model.AgentEmployeeQueryRequest;
import com.dylan.agent.employee.api.model.AgentEmployeeQueryResponse;
import com.dylan.agent.employee.application.AgentEmployeeQueryService;

@RestController
public class AgentEmployeeQueryController {

	private final AgentEmployeeQueryService service;

	public AgentEmployeeQueryController(AgentEmployeeQueryService service) {
		this.service = service;
	}

	@PostMapping("/internal/agent/employee/query")
	public AgentEmployeeQueryResponse query(@AuthenticationPrincipal Jwt jwt,
			@RequestBody AgentEmployeeQueryRequest request) {
		return service.query(request, jwt);
	}

	@ExceptionHandler(AgentBusinessException.class)
	ResponseEntity<AgentBusinessErrorResponse> handle(AgentBusinessException exception) {
		return ResponseEntity.status(exception.status()).body(new AgentBusinessErrorResponse(
				exception.requestId(), exception.code(), "Agent business request failed",
				"abiz-" + UUID.randomUUID()));
	}
}
