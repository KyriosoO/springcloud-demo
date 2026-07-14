package com.dylan.agent.capability.document.provider.security;

/** Provider 外发策略的闭集决策结果。 */
public sealed interface DocumentProviderOutboundPolicyDecisionResult
        permits DocumentProviderOutboundPolicyAllowed, DocumentProviderOutboundPolicyDenied {
}
