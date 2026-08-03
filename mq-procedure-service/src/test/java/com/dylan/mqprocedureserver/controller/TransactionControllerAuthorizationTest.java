package com.dylan.mqprocedureserver.controller;

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
import com.dylan.mqprocedureserver.security.CapabilityAccessGuard;
import com.dylan.mqprocedureserver.service.TransactionOperKafkaProducer;
import com.dylan.mqprocedureserver.service.TransactionOperMQProducer;
import com.dylan.mqprocedureserver.service.TransactionService;
import com.dylan.transaction.api.model.Transaction;
import com.dylan.transaction.api.query.TransactionSearchRequest;
import com.dylan.transaction.api.query.TransactionSearchResponse;

class TransactionControllerAuthorizationTest {

	@Test
	void adminAndViewerReachSearchServiceExactlyOnce() {
		for (String authority : List.of("ROLE_ADMIN", "ROLE_VIEWER")) {
			TransactionService service = mock(TransactionService.class);
			TransactionSearchRequest request = request();
			TransactionSearchResponse expected = new TransactionSearchResponse();
			when(service.search(request)).thenReturn(expected);
			TransactionController controller = controller(service);
			assertThat(controller.search(authentication(authority), request)).isSameAs(expected);
			verify(service).search(request);
		}
	}

	@Test
	void disallowedAuthorityNeverReachesSearchService() {
		TransactionService service = mock(TransactionService.class);
		TransactionController controller = controller(service);
		assertThatThrownBy(() -> controller.search(authentication("ROLE_OTHER"), request()))
				.isInstanceOf(ResponseStatusException.class);
		verifyNoInteractions(service);
	}

	private static TransactionController controller(TransactionService service) {
		return new TransactionController(mock(TransactionOperKafkaProducer.class),
				mock(TransactionOperMQProducer.class), service, new CapabilityAccessGuard());
	}

	private static TransactionSearchRequest request() {
		TransactionSearchRequest request = new TransactionSearchRequest();
		Transaction condition = new Transaction();
		condition.setTransId("synthetic-id");
		request.setCondition(condition);
		request.setPage(1);
		request.setSize(20);
		return request;
	}

	private static JwtAuthenticationToken authentication(String authority) {
		Instant now = Instant.parse("2026-08-03T00:00:00Z");
		Jwt jwt = Jwt.withTokenValue("token").header("alg", "none").subject("synthetic-user")
				.issuedAt(now).expiresAt(now.plusSeconds(300))
				.claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, SecurityTokenUtils.USER_TOKEN_TYPE).build();
		return new JwtAuthenticationToken(jwt, List.of(new SimpleGrantedAuthority(authority)));
	}
}
