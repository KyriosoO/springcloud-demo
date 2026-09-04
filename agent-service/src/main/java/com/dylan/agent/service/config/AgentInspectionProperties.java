package com.dylan.agent.service.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("agent.inspection")
public record AgentInspectionProperties(boolean enabled) {
}
