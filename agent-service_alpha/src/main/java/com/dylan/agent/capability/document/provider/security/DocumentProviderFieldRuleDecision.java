package com.dylan.agent.capability.document.provider.security;

import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.policy.model.SecurityClassificationRef;
import com.dylan.agent.model.MaskType;

import java.util.Objects;

public record DocumentProviderFieldRuleDecision(
        CanonicalFieldRef field,
        SecurityClassificationRef classification,
        MaskType maskType) {
    public DocumentProviderFieldRuleDecision {
        Objects.requireNonNull(field, "field must not be null");
        Objects.requireNonNull(classification, "classification must not be null");
        Objects.requireNonNull(maskType, "maskType must not be null");
    }
}
