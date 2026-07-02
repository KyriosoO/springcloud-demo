package com.dylan.agent.metadata.policy.model;

/** 即使 CHAT 将 delegation 视为不适用，也必须显式表达 delegation limits。 */
public record DelegationLimits(int maxDepth, int maxTasks) {
    public DelegationLimits {
        if (maxDepth < 0 || maxTasks < 0) {
            throw new IllegalArgumentException("delegation limits must be non-negative");
        }
    }
}
