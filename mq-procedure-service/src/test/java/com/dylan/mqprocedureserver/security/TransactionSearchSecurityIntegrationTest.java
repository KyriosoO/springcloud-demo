package com.dylan.mqprocedureserver.security;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import reactor.core.publisher.Mono;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.reactive.WebFluxTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.reactive.server.WebTestClient;

import com.dylan.common.security.SecurityTokenUtils;
import com.dylan.common.security.UserRoleAuthorityAutoConfiguration;
import com.dylan.mqprocedureserver.config.TransactionSearchJsonConfiguration;
import com.dylan.mqprocedureserver.controller.TransactionController;
import com.dylan.mqprocedureserver.mapper.TransactionMapper;
import com.dylan.mqprocedureserver.service.TransactionOperKafkaProducer;
import com.dylan.mqprocedureserver.service.TransactionOperMQProducer;
import com.dylan.mqprocedureserver.service.TransactionService;
import com.dylan.transaction.api.query.TransactionSearchResponse;

@WebFluxTest(TransactionController.class)
@ContextConfiguration(classes = TransactionController.class)
@Import({ TransactionSearchSecurityConfiguration.class, CapabilityAccessGuard.class,
		UserRoleAuthorityAutoConfiguration.class, TransactionSearchJsonConfiguration.class })
@TestPropertySource(properties = { "spring.cloud.config.enabled=false", "spring.config.import=" })
class TransactionSearchSecurityIntegrationTest {
	@Autowired
	private WebTestClient client;
	@MockitoBean
	private ReactiveJwtDecoder jwtDecoder;
	@MockitoBean
	private TransactionService transactionService;
	@MockitoBean
	private TransactionOperKafkaProducer kafkaProducer;
	@MockitoBean
	private TransactionOperMQProducer mqProducer;
	@MockitoBean
	private TransactionMapper transactionMapper;

	@Test
	void adminAndViewerCanSearch() {
		for (String role : List.of("ADMIN", "VIEWER")) {
			when(jwtDecoder.decode("token-" + role)).thenReturn(Mono.just(jwt("user", List.of(role))));
			TransactionSearchResponse response = new TransactionSearchResponse();
			response.setRows(List.of());
			response.setPage(1);
			response.setSize(20);
			when(transactionService.search(any())).thenReturn(response);
			client.post().uri("/txn/search")
					.header(HttpHeaders.AUTHORIZATION, "Bearer token-" + role)
					.header(HttpHeaders.CONTENT_TYPE, "application/json")
					.bodyValue(searchBody())
					.exchange().expectStatus().isOk();
		}
		verify(transactionService, org.mockito.Mockito.times(2)).search(any());
	}

	@Test
	void invalidRoleAndServiceTokenAreRejectedBeforeService() {
		when(jwtDecoder.decode("unknown")).thenReturn(Mono.just(jwt("user", List.of("UNKNOWN"))));
		when(jwtDecoder.decode("service")).thenReturn(Mono.just(jwt("service", List.of("ADMIN"))));
		client.post().uri("/txn/search").header(HttpHeaders.AUTHORIZATION, "Bearer unknown")
				.header(HttpHeaders.CONTENT_TYPE, "application/json").bodyValue(searchBody())
				.exchange().expectStatus().isForbidden();
		client.post().uri("/txn/search").header(HttpHeaders.AUTHORIZATION, "Bearer service")
				.header(HttpHeaders.CONTENT_TYPE, "application/json").bodyValue(searchBody())
				.exchange().expectStatus().isUnauthorized();
		verify(transactionService, never()).search(any());
	}

	@Test
	void aggregateKeepsTheExistingAuthenticatedUserGuard() {
		when(jwtDecoder.decode("fallback")).thenReturn(Mono.just(jwt("user", List.of("UNKNOWN"))));
		when(transactionService.aggregate(any())).thenReturn(Map.of("totalCount", 1));
		client.post().uri("/txn/aggregate")
				.header(HttpHeaders.AUTHORIZATION, "Bearer fallback")
				.header(HttpHeaders.CONTENT_TYPE, "application/json")
				.bodyValue("{\"condition\":{},\"metrics\":[\"COUNT\"]}")
				.exchange().expectStatus().isOk();
		verify(transactionService).aggregate(any());
	}

	@Test
	void quotedAmountIsRejectedBeforeTheService() {
		when(jwtDecoder.decode("admin")).thenReturn(Mono.just(jwt("user", List.of("ADMIN"))));
		client.post().uri("/txn/search")
				.header(HttpHeaders.AUTHORIZATION, "Bearer admin")
				.header(HttpHeaders.CONTENT_TYPE, "application/json")
				.bodyValue("{\"condition\":{\"amount\":\"1.00\"},\"page\":1,\"size\":20}")
				.exchange().expectStatus().isBadRequest();
		verify(transactionService, never()).search(any());
	}

	private static String searchBody() {
		return "{\"condition\":{\"transId\":\"synthetic-id\"},\"page\":1,\"size\":20}";
	}

	private static Jwt jwt(String tokenType, List<String> roles) {
		Instant now = Instant.parse("2026-08-03T00:00:00Z");
		return Jwt.withTokenValue("token").header("alg", "none").subject("synthetic-user")
				.issuedAt(now).expiresAt(now.plusSeconds(300))
				.claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, tokenType)
				.claim("role", roles).build();
	}
}
