package com.dylan.agent.service.application;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.URI;
import java.time.Duration;
import java.time.Instant;

import com.dylan.agent.service.config.AgentIngressProperties;
import com.dylan.agent.service.config.AgentRuntimeProperties;
import com.dylan.agent.service.contract.CapabilityStatus;
import com.dylan.agent.service.contract.RuntimeInvokeRequest;
import com.dylan.agent.service.contract.RuntimeInvokeResponse;
import com.dylan.agent.service.runtime.AgentRuntimeClient;
import com.dylan.agent.service.security.AgentUserContextFactory;
import com.dylan.agent.service.web.AgentRequestMetadata;
import com.dylan.common.security.SecurityTokenUtils;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.security.oauth2.jwt.Jwt;

import reactor.core.publisher.Mono;
import reactor.test.StepVerifier;

class AgentQueryApplicationServiceTest {

    @ParameterizedTest
    @ValueSource(ints = {5, 60, 120})
    void derivesSubDeadlineFromEarliestReceiptForEverySupportedTotalTimeout(int timeoutSeconds) {
        CapturingClient client = new CapturingClient();
        AgentIngressProperties ingress = ingress(Duration.ofSeconds(timeoutSeconds));
        AgentRequestLimiter limiter = new AgentRequestLimiter(ingress);
        AgentQueryApplicationService service = service(
                client, limiter, new FixedClocks(1_100_000_000L, 100_000L), ingress);

        StepVerifier.create(service.query(
                        new AgentQueryCommand("question"),
                        jwt("dylan", "user", "token"),
                        new AgentRequestMetadata("req-budget", "corr-budget", 1_000_000_000L)))
                .expectNextCount(1)
                .verifyComplete();

        int expectedRemainingMillis = timeoutSeconds * 1_000 - 600;
        assertThat(client.request.remainingTimeoutMs()).isEqualTo(expectedRemainingMillis);
        assertThat(client.request.deadlineEpochMs()).isEqualTo(100_000L + expectedRemainingMillis);
        assertThat(client.calls).isEqualTo(1);
        assertThat(limiter.inFlight()).isZero();
    }

    @Test
    void invokesRuntimeOnceWithNormalizedQuestionAndDerivedSubDeadline() {
        CapturingClient client = new CapturingClient();
        FixedClocks clocks = new FixedClocks(1_100_000_000L, 100_000L);
        AgentRequestLimiter limiter = new AgentRequestLimiter(ingress());
        AgentQueryApplicationService service = service(client, limiter, clocks);
        AgentRequestMetadata metadata = new AgentRequestMetadata("req-1", "corr-1", 1_000_000_000L);

        StepVerifier.create(service.query(new AgentQueryCommand("  税务政策  "), jwt("dylan", "user", "token"), metadata))
                .assertNext(response -> {
                    assertThat(response.status()).isEqualTo(CapabilityStatus.NO_RESULT);
                    assertThat(response.requestId()).isEqualTo("req-1");
                })
                .verifyComplete();

        assertThat(client.calls).isEqualTo(1);
        assertThat(client.request.question()).isEqualTo("税务政策");
        assertThat(client.request.remainingTimeoutMs()).isEqualTo(59_400);
        assertThat(client.request.deadlineEpochMs()).isEqualTo(159_400L);
        assertThat(client.rawToken).isEqualTo("token");
        assertThat(limiter.inFlight()).isZero();
    }

    @Test
    void rejectsServiceIdentityAndExpiredOuterBudgetWithoutRuntimeCall() {
        CapturingClient client = new CapturingClient();
        AgentRequestLimiter limiter = new AgentRequestLimiter(ingress());
        AgentRequestMetadata metadata = new AgentRequestMetadata("req-1", "corr-1", 1_000_000_000L);

        StepVerifier.create(service(client, limiter, new FixedClocks(1_100_000_000L, 100_000L))
                        .query(new AgentQueryCommand("question"), jwt("svc", "service", "token"), metadata))
                .expectError(AgentPublicException.class)
                .verify();
        StepVerifier.create(service(client, limiter, new FixedClocks(61_000_000_000L, 100_000L))
                        .query(new AgentQueryCommand("question"), jwt("dylan", "user", "token"), metadata))
                .expectError(AgentPublicException.class)
                .verify();

        assertThat(client.calls).isZero();
        assertThat(limiter.inFlight()).isZero();
    }

    private AgentQueryApplicationService service(
            AgentRuntimeClient client,
            AgentRequestLimiter limiter,
            AgentClocks clocks) {
        return service(client, limiter, clocks, ingress());
    }

    private AgentQueryApplicationService service(
            AgentRuntimeClient client,
            AgentRequestLimiter limiter,
            AgentClocks clocks,
            AgentIngressProperties ingress) {
        return new AgentQueryApplicationService(
                new AgentUserContextFactory(ingress),
                new AgentQuestionValidator(ingress),
                limiter,
                client,
                ingress,
                runtimeProperties(),
                clocks);
    }

    private AgentIngressProperties ingress() {
        return ingress(Duration.ofSeconds(60));
    }

    private AgentIngressProperties ingress(Duration timeout) {
        return new AgentIngressProperties(4096, 32768, 16384, 8, timeout, Duration.ofMillis(500));
    }

    private AgentRuntimeProperties runtimeProperties() {
        return new AgentRuntimeProperties(URI.create("http://127.0.0.1:8091"), 1,
                Duration.ofSeconds(1), 393216);
    }

    private Jwt jwt(String subject, String type, String token) {
        return Jwt.withTokenValue(token)
                .header("alg", "none")
                .subject(subject)
                .claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, type)
                .issuedAt(Instant.now())
                .expiresAt(Instant.now().plusSeconds(60))
                .build();
    }

    private static final class CapturingClient implements AgentRuntimeClient {
        private int calls;
        private String rawToken;
        private RuntimeInvokeRequest request;

        @Override
        public Mono<RuntimeInvokeResponse> invoke(RuntimeInvokeRequest request, String rawUserToken) {
            calls++;
            this.request = request;
            this.rawToken = rawUserToken;
            return Mono.just(new RuntimeInvokeResponse(
                    1, request.requestId(), CapabilityStatus.NO_RESULT, null,
                    "未找到符合条件的结果。", null, null));
        }
    }

    private record FixedClocks(long monotonicNanos, long epochMillis) implements AgentClocks {
    }
}
