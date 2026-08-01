package com.dylan.agent.service.runtime;

import java.time.Duration;

import com.dylan.agent.service.config.AgentRuntimeProperties;

import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.ReactiveHealthIndicator;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

import reactor.core.publisher.Mono;

@Component("agentRuntime")
public final class AgentRuntimeHealthIndicator implements ReactiveHealthIndicator {
    private final WebClient client;

    public AgentRuntimeHealthIndicator(AgentRuntimeProperties properties) {
        this.client = WebClient.builder().baseUrl(properties.baseUrl().toString()).build();
    }

    @Override
    public Mono<Health> health() {
        return client.get().uri("/internal/health/ready")
                .exchangeToMono(response -> response.releaseBody()
                        .thenReturn(response.statusCode() == HttpStatus.OK ? Health.up().build() : Health.down().build()))
                .timeout(Duration.ofMillis(500))
                .onErrorReturn(Health.down().build());
    }
}
