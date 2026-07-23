package com.dylan.agent.employee.security;

import java.time.Instant;

import org.springframework.http.HttpStatus;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Component;

import com.dylan.agent.employee.api.AgentBusinessException;
import com.dylan.agent.employee.api.model.AgentEmployeeQueryRequest;
import com.dylan.agent.employee.config.AgentEmployeeAdapterProperties;

@Component
public class AgentEmployeeDelegatedAuthorization {

	private final AgentEmployeeAdapterProperties properties;

	public AgentEmployeeDelegatedAuthorization(AgentEmployeeAdapterProperties properties) {
		this.properties = properties;
	}

	public void verify(Jwt jwt, AgentEmployeeQueryRequest request) {
		properties.validate();
		if (request == null) {
			throw new AgentBusinessException("AGENT_BUSINESS_INVALID_REQUEST", HttpStatus.BAD_REQUEST);
		}
		if (!properties.isEnabled()) {
			throw new AgentBusinessException("AGENT_BUSINESS_UNAVAILABLE", HttpStatus.SERVICE_UNAVAILABLE,
					request == null ? "" : request.requestId());
		}
		String typ = jwt == null ? null : String.valueOf(jwt.getHeaders().get("typ"));
		String scope = jwt == null ? null : jwt.getClaimAsString("scope");
		if (jwt == null
				|| !"agent-business-delegated+jwt".equals(typ)
				|| !jwt.getAudience().contains(properties.getDelegatedAudience())
				|| !"agent-service".equals(jwt.getSubject())
				|| scope == null || !java.util.Set.of(scope.split("\\s+")).contains("employee.query")
				|| !request.requestId().equals(jwt.getId())
				|| !request.requestId().equals(jwt.getClaimAsString("requestId"))
				|| !"EMPLOYEE".equals(jwt.getClaimAsString("domain"))
				|| !"QUERY".equals(jwt.getClaimAsString("capability"))
				|| !"SINGLE_TENANT_ALL".equals(jwt.getClaimAsString("resourceScopeMode"))
				|| !properties.getSingleTenantRef().equals(jwt.getClaimAsString("tenantRef"))
				|| !AgentEmployeeRequestDigest.sha256(request).equals(jwt.getClaimAsString("requestDigest"))
				|| request.deadlineAt() == null || !request.deadlineAt().isAfter(Instant.now())
				|| jwt.getExpiresAt() == null || jwt.getExpiresAt().isAfter(request.deadlineAt().plusSeconds(1))) {
			throw new AgentBusinessException("AGENT_BUSINESS_FORBIDDEN", HttpStatus.FORBIDDEN,
					request == null ? "" : request.requestId());
		}
	}
}
