package com.dylan.agent.service.security;

import com.dylan.agent.service.application.AgentPublicException;
import com.dylan.agent.service.config.AgentIngressProperties;
import com.dylan.common.security.SecurityTokenUtils;

import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Component;

@Component
public final class AgentUserContextFactory {
    private final int maximumTokenBytes;

    public AgentUserContextFactory(AgentIngressProperties properties) {
        this.maximumTokenBytes = properties.maxUserTokenBytes();
    }

    public AgentUserContext requireUser(Jwt jwt) {
        if (jwt == null || !SecurityTokenUtils.isUserToken(jwt)) {
            throw AgentPublicException.unauthenticated();
        }
        String subject = jwt.getSubject();
        if (subject == null || subject.isBlank()
                || subject.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > 256) {
            throw AgentPublicException.unauthenticated();
        }
        String rawToken = jwt.getTokenValue();
        if (rawToken == null || rawToken.isEmpty()
                || rawToken.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > maximumTokenBytes) {
            throw AgentPublicException.unauthenticated();
        }
        return new AgentUserContext(subject, jwt, maximumTokenBytes);
    }
}
