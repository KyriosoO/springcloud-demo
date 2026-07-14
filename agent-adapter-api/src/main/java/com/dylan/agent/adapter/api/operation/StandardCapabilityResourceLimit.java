package com.dylan.agent.adapter.api.operation;

/** Query/Aggregate/Preview 当前共享的表格型资源上界。 */
public record StandardCapabilityResourceLimit(
        int maxPageSize,
        int maxResultRows,
        long maxResultBytes) implements CapabilityResourceLimit {

    public StandardCapabilityResourceLimit {
        if (maxPageSize < 0 || maxResultRows < 0 || maxResultBytes < 0) {
            throw new IllegalArgumentException("standard capability resource limits must be non-negative");
        }
    }
}
