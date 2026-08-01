package com.dylan.agent.service.security;

public final class AgentUserContext {
    private final int maximumTokenBytes;
    private final org.springframework.security.oauth2.jwt.Jwt jwt;
    private final String subjectId;

    AgentUserContext(String subjectId, org.springframework.security.oauth2.jwt.Jwt jwt, int maximumTokenBytes) {
        this.subjectId = subjectId;
        this.jwt = jwt;
        this.maximumTokenBytes = maximumTokenBytes;
    }

    public String subjectId() {
        return subjectId;
    }

    public String rawTokenForRuntime() {
        String rawToken = jwt.getTokenValue();
        if (rawToken == null || rawToken.isEmpty()
                || rawToken.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > maximumTokenBytes) {
            throw com.dylan.agent.service.application.AgentPublicException.unauthenticated();
        }
        return rawToken;
    }

    @Override
    public String toString() {
        return "AgentUserContext[redacted]";
    }
}
