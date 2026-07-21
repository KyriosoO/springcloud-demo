package com.dylan.agent.kernel.resource;

import com.dylan.agent.adapter.api.operation.StandardCapabilityResourceLimit;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Set;

/** StandardCapabilityResourceLimit@1.0.0 的单调求交规则。 */
public final class StandardCapabilityResourceLimitContract
        implements CapabilityResourceLimitContract<StandardCapabilityResourceLimit> {

    @Override
    public ContractRef contractRef() { return AgentExecutionContracts.STANDARD_RESOURCE_LIMIT; }

    @Override
    public Class<StandardCapabilityResourceLimit> limitType() {
        return StandardCapabilityResourceLimit.class;
    }

    @Override
    public Set<ResourceLimitDimension> supportedDimensions() {
        return StandardCapabilityResourceLimitDimensions.ALL;
    }

    @Override
    public void validate(StandardCapabilityResourceLimit value) {
        if (value == null) {
            throw new IllegalArgumentException("standard resource limit must not be null");
        }
    }

    @Override
    public StandardCapabilityResourceLimit intersect(
            StandardCapabilityResourceLimit left,
            StandardCapabilityResourceLimit right) {
        validate(left);
        validate(right);
        return new StandardCapabilityResourceLimit(
                Math.min(left.maxPageSize(), right.maxPageSize()),
                Math.min(left.maxResultRows(), right.maxResultRows()),
                Math.min(left.maxResultBytes(), right.maxResultBytes()));
    }

    @Override
    public boolean isSameOrStricter(
            StandardCapabilityResourceLimit candidate,
            StandardCapabilityResourceLimit baseline) {
        validate(candidate);
        validate(baseline);
        return candidate.maxPageSize() <= baseline.maxPageSize()
                && candidate.maxResultRows() <= baseline.maxResultRows()
                && candidate.maxResultBytes() <= baseline.maxResultBytes();
    }

    @Override
    public String canonicalDigest(StandardCapabilityResourceLimit value) {
        validate(value);
        String canonical = "StandardCapabilityResourceLimit@1.0.0|"
                + value.maxPageSize() + "|" + value.maxResultRows() + "|" + value.maxResultBytes();
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(canonical.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }
}
