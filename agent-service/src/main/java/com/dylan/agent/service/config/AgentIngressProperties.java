package com.dylan.agent.service.config;

import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("agent.ingress")
public record AgentIngressProperties(
        int maxQuestionChars,
        int maxBodyBytes,
        int maxUserTokenBytes,
        int maxInFlight,
        Duration totalTimeout,
        Duration responseReserve) {

    public AgentIngressProperties {
        requireRange("max-question-chars", maxQuestionChars, 256, 4096);
        requireRange("max-body-bytes", maxBodyBytes, 4096, 65536);
        if (maxUserTokenBytes != 16384) {
            throw new IllegalArgumentException("agent.ingress.max-user-token-bytes");
        }
        requireRange("max-in-flight", maxInFlight, 1, 32);
        requireDuration("total-timeout", totalTimeout, Duration.ofSeconds(5), Duration.ofSeconds(120));
        requireDuration("response-reserve", responseReserve, Duration.ofMillis(100), Duration.ofSeconds(2));
        if (responseReserve.compareTo(totalTimeout) >= 0) {
            throw new IllegalArgumentException("agent.ingress.response-reserve");
        }
    }

    private static void requireRange(String name, int value, int minimum, int maximum) {
        if (value < minimum || value > maximum) {
            throw new IllegalArgumentException("agent.ingress." + name);
        }
    }

    private static void requireDuration(String name, Duration value, Duration minimum, Duration maximum) {
        if (value == null || value.compareTo(minimum) < 0 || value.compareTo(maximum) > 0) {
            throw new IllegalArgumentException("agent.ingress." + name);
        }
    }
}
