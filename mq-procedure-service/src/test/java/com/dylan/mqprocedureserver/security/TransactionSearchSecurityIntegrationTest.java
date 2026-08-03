package com.dylan.mqprocedureserver.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.List;
import java.util.Map;

import reactor.core.publisher.Mono;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.test.autoconfigure.web.reactive.WebFluxTest;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.core.convert.converter.Converter;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
import org.springframework.security.oauth2.server.resource.authentication.ReactiveJwtAuthenticationConverterAdapter;
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
@ExtendWith(OutputCaptureExtension.class)
class TransactionSearchSecurityIntegrationTest {
	private static final String SENSITIVE_TOKEN = "sensitive-transaction-token";
	private static final String SENSITIVE_SUBJECT = "sensitive-transaction-subject";
	private static final String SENSITIVE_ROLE = "SENSITIVE_TRANSACTION_ROLE";
	private static final String SENSITIVE_TRANSACTION_ID = "sensitive-transaction-id";
	@Autowired
	private WebTestClient client;
	@Autowired
	@Qualifier("reactiveUserRoleJwtAuthenticationConverter")
	private Converter<Jwt, Mono<AbstractAuthenticationToken>> userRoleConverter;
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
	void usesTheSharedReactiveAdapterWithoutProviderOverride() {
		assertThat(userRoleConverter)
				.isInstanceOf(ReactiveJwtAuthenticationConverterAdapter.class);
	}

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
	void rejectedRequestsDoNotReachServiceOrLeakSensitiveValues(CapturedOutput output) {
		when(jwtDecoder.decode(SENSITIVE_TOKEN))
				.thenReturn(Mono.just(jwt(SENSITIVE_TOKEN, SENSITIVE_SUBJECT, "user", List.of(SENSITIVE_ROLE))));
		when(jwtDecoder.decode("sensitive-transaction-service-token"))
				.thenReturn(Mono.just(jwt("sensitive-transaction-service-token",
						"sensitive-transaction-service-subject", "service", List.of("ADMIN"))));
		byte[] forbidden = client.post().uri("/txn/search")
				.header(HttpHeaders.AUTHORIZATION, "Bearer " + SENSITIVE_TOKEN)
				.header(HttpHeaders.CONTENT_TYPE, "application/json").bodyValue(sensitiveSearchBody())
				.exchange().expectStatus().isForbidden().expectBody().returnResult().getResponseBody();
		byte[] unauthorized = client.post().uri("/txn/search")
				.header(HttpHeaders.AUTHORIZATION, "Bearer sensitive-transaction-service-token")
				.header(HttpHeaders.CONTENT_TYPE, "application/json").bodyValue(sensitiveSearchBody())
				.exchange().expectStatus().isUnauthorized().expectBody().returnResult().getResponseBody();
		client.post().uri("/txn/search")
				.header(HttpHeaders.CONTENT_TYPE, "application/json").bodyValue(sensitiveSearchBody())
				.exchange().expectStatus().isUnauthorized();
		verify(transactionService, never()).search(any());
		assertNoSensitiveValues(responseText(forbidden));
		assertNoSensitiveValues(responseText(unauthorized));
		assertNoSensitiveValues(output.getAll());
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

	private static String sensitiveSearchBody() {
		return searchBody().replace("synthetic-id", SENSITIVE_TRANSACTION_ID);
	}

	private static String responseText(byte[] body) {
		return body == null ? "" : new String(body, StandardCharsets.UTF_8);
	}

	private static void assertNoSensitiveValues(String actual) {
		assertThat(actual).doesNotContain(SENSITIVE_TOKEN, SENSITIVE_SUBJECT, SENSITIVE_ROLE,
				SENSITIVE_TRANSACTION_ID, "sensitive-transaction-service-token",
				"sensitive-transaction-service-subject");
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
}
