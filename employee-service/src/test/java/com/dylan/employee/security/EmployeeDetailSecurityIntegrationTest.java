package com.dylan.employee.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;
import java.io.InputStream;
import java.lang.reflect.Method;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.core.convert.converter.Converter;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import com.dylan.common.security.SecurityTokenUtils;
import com.dylan.common.security.UserRoleAuthorityAutoConfiguration;
import com.dylan.common.security.UserRoleJwtAuthenticationConverter;
import com.dylan.employee.controller.EmployeeController;
import com.dylan.employee.model.Employee;
import com.dylan.employee.mapper.EmployeeMapper;
import com.dylan.employee.dao.EmployeeChangeRequestMapper;
import com.dylan.employee.dao.EmployeeWorkflowInboxMessageMapper;
import com.dylan.employee.service.EmployeeService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

@WebMvcTest(EmployeeController.class)
@Import({ EmployeeDetailSecurityConfiguration.class, CapabilityAccessGuard.class,
		UserRoleAuthorityAutoConfiguration.class })
@TestPropertySource(properties = { "spring.cloud.config.enabled=false", "spring.config.import=" })
@ExtendWith(OutputCaptureExtension.class)
class EmployeeDetailSecurityIntegrationTest {
	private static final String SENSITIVE_TOKEN = "sensitive-employee-token";
	private static final String SENSITIVE_SUBJECT = "sensitive-employee-subject";
	private static final String SENSITIVE_ROLE = "SENSITIVE_EMPLOYEE_ROLE";
	private static final String SENSITIVE_ID = "sensitive-employee-id";
	@Autowired
	private MockMvc mvc;
	@Autowired
	private ObjectMapper objectMapper;
	@Autowired
	@Qualifier("userRoleJwtAuthenticationConverter")
	private Converter<Jwt, AbstractAuthenticationToken> userRoleConverter;
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
	void usesTheSharedServletConverterWithoutProviderOverride() {
		assertThat(userRoleConverter)
				.isInstanceOf(UserRoleJwtAuthenticationConverter.class);
	}

	@Test
	void adminAndViewerCanReadDetail() throws Exception {
		Set<String> expectedFields = visibilityFields();
		for (String role : List.of("ADMIN", "VIEWER")) {
			when(jwtDecoder.decode("token-" + role)).thenReturn(jwt("user", List.of(role)));
			when(employeeService.detail("synthetic-id")).thenReturn(allFieldsSynthetic());
			MvcResult result = mvc.perform(get("/employees/synthetic-id")
					.header(HttpHeaders.AUTHORIZATION, "Bearer token-" + role))
					.andExpect(status().isOk()).andReturn();
			Set<String> actualFields = new TreeSet<>();
			objectMapper.readTree(result.getResponse().getContentAsByteArray())
					.fieldNames().forEachRemaining(actualFields::add);
			assertThat(actualFields).containsExactlyElementsOf(expectedFields);
		}
		verify(employeeService, org.mockito.Mockito.times(2)).detail("synthetic-id");
	}

	@Test
	void existingNotFoundFailureRemainsBadRequest() throws Exception {
		when(jwtDecoder.decode("admin")).thenReturn(jwt("user", List.of("ADMIN")));
		when(employeeService.detail("missing-id"))
				.thenThrow(new IllegalArgumentException("Employee not found: missing-id"));
		mvc.perform(get("/employees/missing-id")
				.header(HttpHeaders.AUTHORIZATION, "Bearer admin"))
				.andExpect(status().isBadRequest());
		verify(employeeService).detail("missing-id");
	}

	@Test
	void rejectedRequestsDoNotReachServiceOrLeakSensitiveValues(CapturedOutput output) throws Exception {
		when(jwtDecoder.decode(SENSITIVE_TOKEN))
				.thenReturn(jwt(SENSITIVE_TOKEN, SENSITIVE_SUBJECT, "user", List.of(SENSITIVE_ROLE)));
		when(jwtDecoder.decode("sensitive-employee-service-token"))
				.thenReturn(jwt("sensitive-employee-service-token", "sensitive-employee-service-subject",
						"service", List.of("ADMIN")));
		when(jwtDecoder.decode("mixed-role-token"))
				.thenReturn(jwt("mixed-role-token", "mixed-role-subject",
						"user", List.of("ADMIN", "UNKNOWN")));
		MvcResult forbidden = mvc.perform(get("/employees/" + SENSITIVE_ID)
				.header(HttpHeaders.AUTHORIZATION, "Bearer " + SENSITIVE_TOKEN))
				.andExpect(status().isForbidden()).andReturn();
		MvcResult unauthorized = mvc.perform(get("/employees/" + SENSITIVE_ID)
				.header(HttpHeaders.AUTHORIZATION, "Bearer sensitive-employee-service-token"))
				.andExpect(status().isUnauthorized()).andReturn();
		MvcResult mixedRole = mvc.perform(get("/employees/" + SENSITIVE_ID)
				.header(HttpHeaders.AUTHORIZATION, "Bearer mixed-role-token"))
				.andExpect(status().isForbidden()).andReturn();
		mvc.perform(get("/employees/" + SENSITIVE_ID)).andExpect(status().isUnauthorized());
		verify(employeeService, never()).detail(SENSITIVE_ID);
		assertNoSensitiveValues(forbidden.getResponse().getContentAsString());
		assertNoSensitiveValues(unauthorized.getResponse().getContentAsString());
		assertNoSensitiveValues(mixedRole.getResponse().getContentAsString());
		assertNoSensitiveValues(output.getAll());
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
		return jwt("token", "synthetic-user", tokenType, roles);
	}

	private static Jwt jwt(String tokenValue, String subject, String tokenType, List<String> roles) {
		Instant now = Instant.parse("2026-08-03T00:00:00Z");
		return Jwt.withTokenValue(tokenValue).header("alg", "none").subject(subject)
				.issuedAt(now).expiresAt(now.plusSeconds(300))
				.claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, tokenType)
				.claim("role", roles).build();
	}

	private static void assertNoSensitiveValues(String actual) {
		assertThat(actual).doesNotContain(SENSITIVE_TOKEN, SENSITIVE_SUBJECT, SENSITIVE_ROLE, SENSITIVE_ID,
				"sensitive-employee-service-token", "sensitive-employee-service-subject",
				"mixed-role-token", "mixed-role-subject");
	}

	private Set<String> visibilityFields() throws Exception {
		try (InputStream input = getClass().getResourceAsStream(
				"/contracts/employee-detail-response-visibility-v1.json")) {
			JsonNode fixture = objectMapper.readTree(input);
			Set<String> fields = new TreeSet<>();
			fixture.path("fields").forEach(node -> fields.add(node.asText()));
			return fields;
		}
	}

	private static Employee allFieldsSynthetic() throws Exception {
		Employee employee = new Employee();
		for (Method method : Employee.class.getMethods()) {
			if (method.getName().startsWith("set") && method.getParameterCount() == 1
					&& method.getParameterTypes()[0] == String.class) {
				method.invoke(employee, "synthetic-" + method.getName());
			}
		}
		return employee;
	}
}
