package com.dylan.mqprocedureserver.security;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;

class TransactionSearchSecurityConfigurationTest {

	@Test
	void matcherSelectsOnlyPostTransactionSearch() {
		assertThat(matches("POST", "/txn/search")).isTrue();
		assertThat(matches("GET", "/txn/search")).isFalse();
		assertThat(matches("POST", "/txn/aggregate")).isFalse();
		assertThat(matches("POST", "/txn/query")).isFalse();
	}

	private static boolean matches(String method, String path) {
		MockServerHttpRequest request = MockServerHttpRequest.method(
				org.springframework.http.HttpMethod.valueOf(method), path).build();
		return TransactionSearchSecurityConfiguration.transactionSearchMatcher()
				.matches(MockServerWebExchange.from(request)).block().isMatch();
	}
}
