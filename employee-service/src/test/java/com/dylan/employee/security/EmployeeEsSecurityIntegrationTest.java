package com.dylan.employee.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.Instant;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.core.convert.converter.Converter;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.oauth2.jwt.BadJwtException;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import com.dylan.common.security.SecurityTokenUtils;
import com.dylan.common.security.UserRoleAuthorityAutoConfiguration;
import com.dylan.common.security.UserRoleJwtAuthenticationConverter;
import com.dylan.employee.controller.EmployeeEsController;
import com.dylan.employee.dao.EmployeeChangeRequestMapper;
import com.dylan.employee.dao.EmployeeWorkflowInboxMessageMapper;
import com.dylan.employee.mapper.EmployeeMapper;
import com.dylan.employee.service.EmployeeEsService;
import com.dylan.esquery.api.model.SearchRequest;
import com.dylan.esquery.api.model.SemanticSearchRequest;

@WebMvcTest(EmployeeEsController.class)
@Import({ EmployeeDetailSecurityConfiguration.class, CapabilityAccessGuard.class,
		UserRoleAuthorityAutoConfiguration.class })
@TestPropertySource(properties = { "spring.cloud.config.enabled=false", "spring.config.import=" })
class EmployeeEsSecurityIntegrationTest {
	private static final List<String> QUERY_ENDPOINTS = List.of(
			"/employees/es/search", "/employees/es/vector-search");

	@Autowired
	private MockMvc mvc;

	@Autowired
	@Qualifier("userRoleJwtAuthenticationConverter")
	private Converter<Jwt, AbstractAuthenticationToken> userRoleConverter;

	@MockitoBean
	private JwtDecoder jwtDecoder;

	@MockitoBean
	private EmployeeEsService employeeEsService;

	@MockitoBean
	private EmployeeMapper employeeMapper;

	@MockitoBean
	private EmployeeChangeRequestMapper employeeChangeRequestMapper;

	@MockitoBean
	private EmployeeWorkflowInboxMessageMapper employeeWorkflowInboxMessageMapper;

	@Test
	void usesTheExistingSharedServletUserRoleConverter() {
		assertThat(userRoleConverter).isInstanceOf(UserRoleJwtAuthenticationConverter.class);
	}

	@Test
	void adminAndViewerRoleClaimsReachBothExistingReadEndpoints() throws Exception {
		when(employeeEsService.search(any(SearchRequest.class))).thenReturn("{}");
		when(employeeEsService.vectorSearch(any(SemanticSearchRequest.class))).thenReturn("{}");

		for (String role : List.of("ADMIN", "VIEWER")) {
			String token = "synthetic-user-" + role;
			when(jwtDecoder.decode(token)).thenReturn(jwt("user", List.of(role)));
			for (String endpoint : QUERY_ENDPOINTS) {
				mvc.perform(post(endpoint)
						.contentType(MediaType.APPLICATION_JSON)
						.content("{}")
						.header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
						.andExpect(status().isOk());
			}
		}

		verify(employeeEsService, times(2)).search(any(SearchRequest.class));
		verify(employeeEsService, times(2)).vectorSearch(any(SemanticSearchRequest.class));
	}

	@Test
	void rejectedRolesAndInvalidTokensNeverReachEitherEmployeeQuery() throws Exception {
		when(jwtDecoder.decode("unknown-role")).thenReturn(jwt("user", List.of("UNKNOWN")));
		when(jwtDecoder.decode("mixed-role")).thenReturn(jwt("user", List.of("ADMIN", "UNKNOWN")));
		when(jwtDecoder.decode("service-token")).thenReturn(jwt("service", List.of("ADMIN")));
		when(jwtDecoder.decode("malformed-token"))
				.thenThrow(new BadJwtException("Invalid synthetic token"));

		for (String endpoint : QUERY_ENDPOINTS) {
			for (String token : List.of("unknown-role", "mixed-role")) {
				mvc.perform(post(endpoint).contentType(MediaType.APPLICATION_JSON).content("{}")
						.header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
						.andExpect(status().isForbidden());
			}
			for (String token : List.of("service-token", "malformed-token")) {
				mvc.perform(post(endpoint).contentType(MediaType.APPLICATION_JSON).content("{}")
						.header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
						.andExpect(status().isUnauthorized());
			}
			mvc.perform(post(endpoint).contentType(MediaType.APPLICATION_JSON).content("{}"))
					.andExpect(status().isUnauthorized());
		}

		verifyNoInteractions(employeeEsService);
	}

	@Test
	void unrelatedEsEndpointKeepsExistingAuthenticatedOnlyFallback() throws Exception {
		when(jwtDecoder.decode("fallback-user")).thenReturn(jwt("user", List.of("UNKNOWN")));
		when(employeeEsService.tasks()).thenReturn(List.of());

		mvc.perform(get("/employees/es/rebuild/tasks")
				.header(HttpHeaders.AUTHORIZATION, "Bearer fallback-user"))
				.andExpect(status().isOk());

		verify(employeeEsService).tasks();
	}

	private static Jwt jwt(String tokenType, List<String> roles) {
		Instant now = Instant.parse("2026-08-25T00:00:00Z");
		return Jwt.withTokenValue("synthetic-user-token")
				.header("alg", "none")
				.subject("synthetic-user")
				.issuedAt(now)
				.expiresAt(now.plusSeconds(300))
				.claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, tokenType)
				.claim("role", roles)
				.build();
	}
}
