package com.dylan.employee.security;

import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import com.dylan.common.security.SecurityTokenUtils;
import com.dylan.common.security.UserRoleAuthorityAutoConfiguration;
import com.dylan.employee.controller.EmployeeController;
import com.dylan.employee.model.Employee;
import com.dylan.employee.mapper.EmployeeMapper;
import com.dylan.employee.dao.EmployeeChangeRequestMapper;
import com.dylan.employee.dao.EmployeeWorkflowInboxMessageMapper;
import com.dylan.employee.service.EmployeeService;

@WebMvcTest(EmployeeController.class)
@Import({ EmployeeDetailSecurityConfiguration.class, CapabilityAccessGuard.class,
		UserRoleAuthorityAutoConfiguration.class })
@TestPropertySource(properties = { "spring.cloud.config.enabled=false", "spring.config.import=" })
class EmployeeDetailSecurityIntegrationTest {
	@Autowired
	private MockMvc mvc;
	@MockitoBean
	private JwtDecoder jwtDecoder;
	@MockitoBean
	private EmployeeService employeeService;
	@MockitoBean
	private EmployeeMapper employeeMapper;
	@MockitoBean
	private EmployeeChangeRequestMapper employeeChangeRequestMapper;
	@MockitoBean
	private EmployeeWorkflowInboxMessageMapper employeeWorkflowInboxMessageMapper;

	@Test
	void adminAndViewerCanReadDetail() throws Exception {
		for (String role : List.of("ADMIN", "VIEWER")) {
			when(jwtDecoder.decode("token-" + role)).thenReturn(jwt("user", List.of(role)));
			when(employeeService.detail("synthetic-id")).thenReturn(new Employee());
			mvc.perform(get("/employees/synthetic-id")
					.header(HttpHeaders.AUTHORIZATION, "Bearer token-" + role))
					.andExpect(status().isOk());
		}
		verify(employeeService, org.mockito.Mockito.times(2)).detail("synthetic-id");
	}

	@Test
	void invalidRoleAndServiceTokenAreRejectedBeforeService() throws Exception {
		when(jwtDecoder.decode("unknown")).thenReturn(jwt("user", List.of("UNKNOWN")));
		when(jwtDecoder.decode("service")).thenReturn(jwt("service", List.of("ADMIN")));
		mvc.perform(get("/employees/synthetic-id")
				.header(HttpHeaders.AUTHORIZATION, "Bearer unknown"))
				.andExpect(status().isForbidden());
		mvc.perform(get("/employees/synthetic-id")
				.header(HttpHeaders.AUTHORIZATION, "Bearer service"))
				.andExpect(status().isUnauthorized());
		verify(employeeService, never()).detail("synthetic-id");
	}

	@Test
	void fallbackEndpointKeepsAuthenticatedUserBehavior() throws Exception {
		when(jwtDecoder.decode("fallback")).thenReturn(jwt("user", List.of("UNKNOWN")));
		when(employeeService.count()).thenReturn(1L);
		mvc.perform(get("/employees/count")
				.header(HttpHeaders.AUTHORIZATION, "Bearer fallback"))
				.andExpect(status().isOk());
		verify(employeeService).count();
	}

	private static Jwt jwt(String tokenType, List<String> roles) {
		Instant now = Instant.parse("2026-08-03T00:00:00Z");
		return Jwt.withTokenValue("token").header("alg", "none").subject("synthetic-user")
				.issuedAt(now).expiresAt(now.plusSeconds(300))
				.claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, tokenType)
				.claim("role", roles).build();
	}
}
