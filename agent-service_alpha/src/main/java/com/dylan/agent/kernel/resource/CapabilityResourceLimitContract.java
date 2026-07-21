package com.dylan.agent.kernel.resource;

import com.dylan.agent.adapter.api.operation.CapabilityResourceLimit;
import com.dylan.agent.api.contract.common.ContractRef;

import java.util.Set;

/** 一个强类型资源限额契约的求交、比较与摘要规则。 */
public interface CapabilityResourceLimitContract<T extends CapabilityResourceLimit> {

    ContractRef contractRef();

    Class<T> limitType();

    Set<ResourceLimitDimension> supportedDimensions();

    void validate(T value);

    T intersect(T left, T right);

    boolean isSameOrStricter(T candidate, T baseline);

    String canonicalDigest(T value);
}
