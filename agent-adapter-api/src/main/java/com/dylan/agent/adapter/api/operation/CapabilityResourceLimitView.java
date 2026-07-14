package com.dylan.agent.adapter.api.operation;

import com.dylan.agent.api.contract.common.ContractRef;

/** Adapter 和 capability-local provider 可消费的最小只读资源限额视图。 */
public interface CapabilityResourceLimitView {

    <T extends CapabilityResourceLimit> T require(ContractRef ref, Class<T> type);

    ResourceLimitReference reference();
}
