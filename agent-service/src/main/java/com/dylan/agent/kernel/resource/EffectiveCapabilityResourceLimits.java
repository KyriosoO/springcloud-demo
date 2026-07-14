package com.dylan.agent.kernel.resource;

import com.dylan.agent.adapter.api.operation.CapabilityResourceLimit;
import com.dylan.agent.adapter.api.operation.CapabilityResourceLimitView;
import com.dylan.agent.adapter.api.operation.ResourceLimitReference;
import com.dylan.agent.api.contract.common.ContractRef;

import java.util.Objects;

/** 请求级冻结后的唯一强类型资源限额。 */
public final class EffectiveCapabilityResourceLimits implements CapabilityResourceLimitView {

    private final ContractRef contractRef;
    private final Class<? extends CapabilityResourceLimit> limitType;
    private final CapabilityResourceLimit value;
    private final String canonicalDigest;
    private final ResourceLimitBindingIdentity bindingIdentity;
    private final ResourceLimitReference reference;

    public <T extends CapabilityResourceLimit> EffectiveCapabilityResourceLimits(
            ContractRef contractRef,
            Class<T> limitType,
            T value,
            String canonicalDigest,
            ResourceLimitBindingIdentity bindingIdentity) {
        this.contractRef = Objects.requireNonNull(contractRef, "contractRef must not be null");
        this.limitType = Objects.requireNonNull(limitType, "limitType must not be null");
        this.value = Objects.requireNonNull(value, "value must not be null");
        if (!limitType.isInstance(value)) {
            throw new IllegalArgumentException("resource limit value type mismatch");
        }
        if (canonicalDigest == null || !canonicalDigest.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("canonicalDigest must be lowercase SHA-256 hex");
        }
        this.canonicalDigest = canonicalDigest;
        this.bindingIdentity = Objects.requireNonNull(bindingIdentity, "bindingIdentity must not be null");
        this.reference = new ResourceLimitReference(
                contractRef,
                canonicalDigest,
                bindingIdentity.invocationId(),
                bindingIdentity.registrationIdentity());
    }

    public ContractRef contractRef() { return contractRef; }

    public Class<? extends CapabilityResourceLimit> limitType() { return limitType; }

    @Override
    public <T extends CapabilityResourceLimit> T require(ContractRef ref, Class<T> type) {
        if (!contractRef.equals(ref) || !limitType.equals(type)) {
            throw new IllegalArgumentException("effective resource limit contract/type mismatch");
        }
        return type.cast(value);
    }

    @Override
    public ResourceLimitReference reference() { return reference; }

    public String canonicalDigest() { return canonicalDigest; }

    public ResourceLimitBindingIdentity bindingIdentity() { return bindingIdentity; }
}
