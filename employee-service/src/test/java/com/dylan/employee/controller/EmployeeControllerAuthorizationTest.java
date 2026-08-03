package com.dylan.employee.controller;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.server.ResponseStatusException;

import com.dylan.common.security.SecurityTokenUtils;
import com.dylan.employee.model.Employee;
import com.dylan.employee.security.CapabilityAccessGuard;
import com.dylan.employee.service.EmployeeService;

class EmployeeControllerAuthorizationTest {

	@Test
	void adminAndViewerReachServiceExactlyOnce() {
		for (String authority : List.of("ROLE_ADMIN", "ROLE_VIEWER")) {
			EmployeeService service = mock(EmployeeService.class);
			Employee expected = new Employee();
			when(service.detail("synthetic-id")).thenReturn(expected);
			EmployeeController controller = new EmployeeController(service, new CapabilityAccessGuard());
			assertThat(controller.detail(authentication(authority), "synthetic-id")).isSameAs(expected);
			verify(service).detail("synthetic-id");
		}
	}

	@Test
	void disallowedAuthorityNeverReachesService() {
		EmployeeService service = mock(EmployeeService.class);
		EmployeeController controller = new EmployeeController(service, new CapabilityAccessGuard());
		assertThatThrownBy(() -> controller.detail(authentication("ROLE_OTHER"), "synthetic-id"))
				.isInstanceOf(ResponseStatusException.class);
		verifyNoInteractions(service);
	}

	private static JwtAuthenticationToken authentication(String authority) {
		Instant now = Instant.parse("2026-08-03T00:00:00Z");
		Jwt jwt = Jwt.withTokenValue("token").header("alg", "none").subject("synthetic-user")
				.issuedAt(now).expiresAt(now.plusSeconds(300))
				.claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, SecurityTokenUtils.USER_TOKEN_TYPE).build();
		return new JwtAuthenticationToken(jwt, List.of(new SimpleGrantedAuthority(authority)));
	}
}
