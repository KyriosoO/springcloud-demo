package com.dylan.agent.capability.document.provider.security;

/** Provider 外发策略的受控拒绝原因。 */
public enum DocumentProviderOutboundPolicyDenialCode {
    INVALID_OPERATION,
    SCOPE_MISSING,
    SCOPE_EXPIRED,
    INVOCATION_BINDING_MISMATCH,
    FEATURE_DISABLED,
    CORPUS_NOT_ALLOWED,
    PURPOSE_NOT_ALLOWED,
    FIELD_NOT_ALLOWED,
    CLASSIFICATION_MISSING,
    CLASSIFICATION_PURPOSE_NOT_ALLOWED,
    MASK_UNKNOWN,
    EVIDENCE_BINDING_MISMATCH
}
