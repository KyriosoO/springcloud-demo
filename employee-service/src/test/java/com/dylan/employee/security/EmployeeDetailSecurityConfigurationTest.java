package com.dylan.employee.security;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.security.web.util.matcher.RequestMatcher;

class EmployeeDetailSecurityConfigurationTest {
	private final RequestMatcher matcher = EmployeeDetailSecurityConfiguration.employeeDetailMatcher();

	@Test
	void matchesOnlyTheExistingGetDetailEndpoint() {
		assertThat(matcher.matches(request("GET", "/employees/synthetic-id"))).isTrue();
		assertThat(matcher.matches(request("GET", "/employees/count"))).isFalse();
		assertThat(matcher.matches(request("GET", "/employees/es/search"))).isFalse();
		assertThat(matcher.matches(request("GET", "/employees/change-requests/1"))).isFalse();
		assertThat(matcher.matches(request("PUT", "/employees/synthetic-id"))).isFalse();
	}

	@Test
	void esQueryMatcherOnlyMatchesTheTwoExistingPostQueryEndpoints() {
		RequestMatcher esQueryMatcher = EmployeeDetailSecurityConfiguration.employeeEsQueryMatcher();
		assertThat(esQueryMatcher.matches(request("POST", "/employees/es/search"))).isTrue();
		assertThat(esQueryMatcher.matches(request("POST", "/employees/es/vector-search"))).isTrue();
		assertThat(esQueryMatcher.matches(request("GET", "/employees/es/search"))).isFalse();
		assertThat(esQueryMatcher.matches(request("POST", "/employees/es/search/more"))).isFalse();
		assertThat(esQueryMatcher.matches(request("POST", "/employees/es/bulk"))).isFalse();
		assertThat(esQueryMatcher.matches(request("GET", "/employees/synthetic-id"))).isFalse();
	}

	private static MockHttpServletRequest request(String method, String path) {
		MockHttpServletRequest request = new MockHttpServletRequest(method, path);
		request.setServletPath(path);
		return request;
	}
}
