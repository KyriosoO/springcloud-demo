package com.dylan.agent.capability.document.provider.security;

import java.util.Objects;

public record DocumentProviderOutboundPolicyDenied(DocumentProviderOutboundPolicyDenialCode reasonCode)
        implements DocumentProviderOutboundPolicyDecisionResult {
    public DocumentProviderOutboundPolicyDenied {
        Objects.requireNonNull(reasonCode, "reasonCode must not be null");
    }
}
