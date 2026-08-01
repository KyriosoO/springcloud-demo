package com.dylan.agent.service.config;

import java.net.URI;
import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("agent.runtime")
public record AgentRuntimeProperties(
        URI baseUrl,
        int contractVersion,
        Duration connectTimeout,
        int maxResponseBytes) {

    public AgentRuntimeProperties {
        if (baseUrl == null || !"http".equals(baseUrl.getScheme()) || baseUrl.getUserInfo() != null
                || baseUrl.getQuery() != null || baseUrl.getFragment() != null
                || (baseUrl.getPath() != null && !baseUrl.getPath().isEmpty())
                || !isLoopback(baseUrl.getHost())) {
            throw new IllegalArgumentException("agent.runtime.base-url");
        }
        if (contractVersion != 1) {
            throw new IllegalArgumentException("agent.runtime.contract-version");
        }
        if (connectTimeout == null || connectTimeout.compareTo(Duration.ofMillis(100)) < 0
                || connectTimeout.compareTo(Duration.ofSeconds(5)) > 0) {
            throw new IllegalArgumentException("agent.runtime.connect-timeout");
        }
        if (maxResponseBytes < 32768 || maxResponseBytes > 524288) {
            throw new IllegalArgumentException("agent.runtime.max-response-bytes");
        }
    }

    private static boolean isLoopback(String host) {
        return "127.0.0.1".equals(host) || "localhost".equalsIgnoreCase(host) || "::1".equals(host);
    }
}
