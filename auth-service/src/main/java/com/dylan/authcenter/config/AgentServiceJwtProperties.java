package com.dylan.authcenter.config;

import java.util.LinkedHashSet;
import java.util.Set;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "agent.security.service-token")
public class AgentServiceJwtProperties {
	private String issuer = "agent-service";
	private String audience = "auth-service";
	private String requiredSubject = "agent-service";
	private Set<String> requiredScopes = new LinkedHashSet<>(Set.of("agent.permission.resolve"));

	public String getIssuer() { return issuer; }
	public void setIssuer(String issuer) { this.issuer = issuer; }
	public String getAudience() { return audience; }
	public void setAudience(String audience) { this.audience = audience; }
	public String getRequiredSubject() { return requiredSubject; }
	public void setRequiredSubject(String requiredSubject) { this.requiredSubject = requiredSubject; }
	public Set<String> getRequiredScopes() { return Set.copyOf(requiredScopes); }
	public void setRequiredScopes(Set<String> requiredScopes) {
		this.requiredScopes = requiredScopes == null ? Set.of() : new LinkedHashSet<>(requiredScopes);
	}
}
