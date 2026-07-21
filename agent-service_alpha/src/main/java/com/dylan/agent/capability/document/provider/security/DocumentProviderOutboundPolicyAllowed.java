package com.dylan.agent.capability.document.provider.security;

import java.util.Objects;

public record DocumentProviderOutboundPolicyAllowed(DocumentProviderOutboundPolicyDecision decision)
        implements DocumentProviderOutboundPolicyDecisionResult {
    public DocumentProviderOutboundPolicyAllowed {
        Objects.requireNonNull(decision, "decision must not be null");
    }
}
