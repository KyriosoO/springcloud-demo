package com.dylan.springgateway.config;

import java.net.URI;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "agent.gateway")
public record AgentGatewayProperties(boolean enabled, URI uri) {

	public AgentGatewayProperties {
		if (enabled && (uri == null || uri.getHost() == null
				|| (!"http".equalsIgnoreCase(uri.getScheme()) && !"https".equalsIgnoreCase(uri.getScheme())))) {
			throw new IllegalArgumentException("agent.gateway.uri must be an absolute http/https URI when enabled");
		}
	}
}
