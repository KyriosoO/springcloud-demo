package com.dylan.agent.service.application;

import com.dylan.agent.service.config.AgentIngressProperties;

import org.springframework.stereotype.Component;

@Component
public final class AgentQuestionValidator {
    private final int maximumCodePoints;

    public AgentQuestionValidator(AgentIngressProperties properties) {
        this.maximumCodePoints = properties.maxQuestionChars();
    }

    public String normalize(String rawQuestion) {
        if (rawQuestion == null) {
            throw AgentPublicException.invalidRequest();
        }
        String normalized = rawQuestion.strip();
        int codePoints = normalized.codePointCount(0, normalized.length());
        if (codePoints < 1 || codePoints > maximumCodePoints) {
            throw AgentPublicException.invalidRequest();
        }
        return normalized;
    }
}
