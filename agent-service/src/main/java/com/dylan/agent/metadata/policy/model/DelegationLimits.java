package com.dylan.agent.metadata.policy.model;

/** Delegation limits are explicit even when CHAT treats them as not applicable. */
public record DelegationLimits(int maxDepth, int maxTasks) {
    public DelegationLimits {
        if (maxDepth < 0 || maxTasks < 0) {
            throw new IllegalArgumentException("delegation limits must be non-negative");
        }
    }
}
