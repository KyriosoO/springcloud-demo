package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.response.AgentResultPayload;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.kernel.resource.EffectiveCapabilityResourceLimits;

public interface ResultSecurityProjector<O extends AgentResultPayload> {
    ContractRef supports();
    Class<O> payloadType();
    FilteredResult<O> filter(
            O candidate,
            ExecutionScope scope,
            EffectiveCapabilityResourceLimits limits);

    default FilteredResult<O> filterUntyped(
            AgentResultPayload candidate,
            ExecutionScope scope,
            EffectiveCapabilityResourceLimits limits) {
        return filter(payloadType().cast(candidate), scope, limits);
    }
}
