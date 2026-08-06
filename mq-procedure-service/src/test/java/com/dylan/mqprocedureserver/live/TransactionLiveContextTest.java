package com.dylan.mqprocedureserver.live;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mockingDetails;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.core.convert.converter.Converter;
import org.springframework.http.HttpHeaders;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import org.springframework.test.web.reactive.server.WebTestClient;

import com.dylan.mqprocedureserver.mapper.TransactionMapper;
import com.dylan.mqprocedureserver.service.TransactionOperKafkaProducer;
import com.dylan.mqprocedureserver.service.TransactionOperMQProducer;
import com.dylan.mqprocedureserver.service.TransactionService;
import com.dylan.transaction.api.model.Transaction;

import reactor.core.publisher.Mono;

@SpringBootTest(
        classes = TransactionRealActionLiveIntegrationTest.LiveApplication.class,
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {
                "spring.main.banner-mode=off",
                "spring.profiles.active=transaction-live-isolated",
                "spring.cloud.config.enabled=false",
                "spring.config.import=",
                "eureka.client.enabled=false",
                "spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration,org.mybatis.spring.boot.autoconfigure.MybatisAutoConfiguration,org.redisson.spring.starter.RedissonAutoConfigurationV2",
                "transaction.search.max-exact-total=10000",
                "common.security.secrets.source-order[0]=config",
                "common.security.secrets.allow-config-values=true",
                "common.security.secrets.fail-fast=true",
                "common.security.secrets.jwt.active-key-id=ACTIVE",
                "common.security.secrets.jwt.keys.ACTIVE.env=",
        })
class TransactionLiveContextTest {
    private static final String TEST_SECRET = randomSecret();

    @LocalServerPort
    private int port;
    @Autowired
    private ReactiveJwtDecoder jwtDecoder;
    @Autowired
    private JwtEncoder jwtEncoder;
    @Autowired
    private WebTestClient client;
    @Autowired
    @Qualifier("reactiveUserRoleJwtAuthenticationConverter")
    private Converter<Jwt, Mono<AbstractAuthenticationToken>> authorityConverter;
    @MockitoBean
    private TransactionMapper transactionMapper;
    @MockitoBean
    private TransactionOperKafkaProducer kafkaProducer;
    @MockitoBean
    private TransactionOperMQProducer mqProducer;
    @MockitoSpyBean
    private TransactionService transactionService;

    @DynamicPropertySource
    static void secretProperty(DynamicPropertyRegistry registry) {
        registry.add("common.security.secrets.jwt.keys.ACTIVE.value", () -> TEST_SECRET);
    }

    @Test
    void minimalLiveApplicationStartsWithoutExternalInfrastructure() {
        assertThat(port).isBetween(1024, 65535);
        assertThat(jwtDecoder).isNotNull();
        assertThat(authorityConverter).isNotNull();
    }

    @Test
    void syntheticAllowedRequestsPreserveDirectSpyAndExactAmountContract() {
        for (String body : List.of(
                "{\"condition\":{\"amount\":0.01},\"page\":1,\"size\":20,\"sorts\":[]}",
                "{\"condition\":{\"amountGt\":-9999999999999999.99},\"page\":1,\"size\":20,\"sorts\":[]}",
                "{\"condition\":{\"amountLt\":9999999999999999.99},\"page\":1,\"size\":20,\"sorts\":[]}")) {
            client.post().uri("/txn/search")
                    .header(HttpHeaders.AUTHORIZATION, "Bearer " + userToken("ADMIN"))
                    .header(HttpHeaders.CONTENT_TYPE, "application/json")
                    .bodyValue(body)
                    .exchange()
                    .expectStatus().isOk();
        }

        var captor = org.mockito.ArgumentCaptor.forClass(Transaction.class);
        verify(transactionMapper, times(3)).countUpTo(captor.capture(), org.mockito.ArgumentMatchers.eq(10001));
        List<Transaction> conditions = captor.getAllValues();
        assertThat(conditions.get(0).getAmount()).isEqualByComparingTo("0.01");
        assertThat(conditions.get(1).getAmountGt()).isEqualByComparingTo("-9999999999999999.99");
        assertThat(conditions.get(2).getAmountLt()).isEqualByComparingTo("9999999999999999.99");
        assertThat(mockingDetails(transactionService).getInvocations().stream()
                .filter(invocation -> invocation.getMethod().getName().equals("search"))).hasSize(3);
        assertThat(mockingDetails(transactionMapper).getInvocations().stream()
                .filter(invocation -> invocation.getMethod().getName().equals("query"))).isEmpty();
        assertThat(mockingDetails(transactionService).getInvocations().stream()
                .filter(invocation -> invocation.getMethod().getDeclaringClass().equals(TransactionService.class))
                .filter(invocation -> java.lang.reflect.Modifier.isPublic(invocation.getMethod().getModifiers()))
                .filter(invocation -> !invocation.getMethod().getName().equals("search"))).isEmpty();
    }

    private String userToken(String role) {
        Instant now = Instant.now();
        JwsHeader header = JwsHeader.with(() -> "HS256").keyId("ACTIVE").build();
        JwtClaimsSet claims = JwtClaimsSet.builder()
                .subject("synthetic-context-user")
                .issuedAt(now)
                .expiresAt(now.plusSeconds(300))
                .claim("token_type", "user")
                .claim("role", List.of(role))
                .build();
        return jwtEncoder.encode(JwtEncoderParameters.from(header, claims)).getTokenValue();
    }

    private static String randomSecret() {
        byte[] bytes = new byte[48];
        new SecureRandom().nextBytes(bytes);
        try {
            return Base64.getEncoder().encodeToString(bytes);
        } finally {
            java.util.Arrays.fill(bytes, (byte) 0);
        }
    }
}
