package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.response.AgentResultPayload;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

public interface ResultSecurityProjector<O extends AgentResultPayload> {
    ContractRef supports();
    Class<O> payloadType();
    FilteredResult<O> filter(O candidate, ExecutionScope scope);
}
