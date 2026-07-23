package com.dylan.agent.employee.security;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jwt.Jwt;

import com.dylan.agent.employee.api.AgentBusinessException;
import com.dylan.agent.employee.api.model.AgentEmployeeField;
import com.dylan.agent.employee.api.model.AgentEmployeeFilter;
import com.dylan.agent.employee.api.model.AgentEmployeeQueryRequest;
import com.dylan.agent.employee.api.model.AgentEmployeeSort;
import com.dylan.agent.employee.api.model.AgentPageRequest;
import com.dylan.agent.employee.api.model.AgentQueryOperator;
import com.dylan.agent.employee.api.model.AgentSortDirection;
import com.dylan.agent.employee.config.AgentEmployeeAdapterProperties;

class AgentEmployeeDelegatedAuthorizationTest {

	@Test
	void acceptsBoundDelegatedTokenForAdapterAudience() {
		AgentEmployeeQueryRequest request = request();
		AgentEmployeeDelegatedAuthorization authorization =
				new AgentEmployeeDelegatedAuthorization(enabledProperties());

		assertThatCode(() -> authorization.verify(token(request, "agent-employee-adapter"), request))
				.doesNotThrowAnyException();
	}

	@Test
	void rejectsLegacyEmployeeServiceAudience() {
		AgentEmployeeQueryRequest request = request();
		AgentEmployeeDelegatedAuthorization authorization =
				new AgentEmployeeDelegatedAuthorization(enabledProperties());

		assertThatThrownBy(() -> authorization.verify(token(request, "employee-service"), request))
				.isInstanceOfSatisfying(AgentBusinessException.class,
						ex -> org.assertj.core.api.Assertions.assertThat(ex.code())
								.isEqualTo("AGENT_BUSINESS_FORBIDDEN"));
	}

	@Test
	void requestDigestMatchesPythonContractFixture() {
		AgentEmployeeQueryRequest request = new AgentEmployeeQueryRequest(
				"00000000-0000-0000-0000-000000000001",
				List.of(new AgentEmployeeFilter(
						AgentEmployeeField.WORK_BASE_SI, AgentQueryOperator.IN,
						List.of("SHANGHAI", "BEIJING"))),
				List.of(AgentEmployeeField.POSITION, AgentEmployeeField.WORK_BASE_SI),
				List.of(new AgentEmployeeSort(AgentEmployeeField.POSITION, AgentSortDirection.DESC)),
				new AgentPageRequest(2, 25),
				Instant.parse("2026-07-24T00:00:00Z"));

		org.assertj.core.api.Assertions.assertThat(AgentEmployeeRequestDigest.sha256(request))
				.isEqualTo("ca52b4e9b06789bd86615bec954b5e5b00bdee33bed3fd7db9a004ada397b0eb");
	}

	private static AgentEmployeeAdapterProperties enabledProperties() {
		AgentEmployeeAdapterProperties properties = new AgentEmployeeAdapterProperties();
		properties.setEnabled(true);
		properties.setSingleTenantRef("tenant-main");
		properties.setDelegatedAudience("agent-employee-adapter");
		return properties;
	}

	private static AgentEmployeeQueryRequest request() {
		return new AgentEmployeeQueryRequest(
				"00000000-0000-0000-0000-000000000001",
				List.of(), List.of(AgentEmployeeField.POSITION), List.of(),
				new AgentPageRequest(0, 10), Instant.now().plusSeconds(60));
	}

	private static Jwt token(AgentEmployeeQueryRequest request, String audience) {
		Instant now = Instant.now();
		return Jwt.withTokenValue("token")
				.header("alg", "HS256")
				.header("typ", "agent-business-delegated+jwt")
				.subject("agent-service")
				.audience(List.of(audience))
				.issuedAt(now)
				.expiresAt(request.deadlineAt())
				.claim("jti", request.requestId())
				.claim("scope", "employee.query")
				.claim("requestId", request.requestId())
				.claim("domain", "EMPLOYEE")
				.claim("capability", "QUERY")
				.claim("resourceScopeMode", "SINGLE_TENANT_ALL")
				.claim("tenantRef", "tenant-main")
				.claim("requestDigest", AgentEmployeeRequestDigest.sha256(request))
				.build();
	}
}
