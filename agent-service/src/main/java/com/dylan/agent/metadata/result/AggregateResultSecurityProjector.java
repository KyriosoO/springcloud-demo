package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.response.AggregateAgentResultPayload;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

/** Aggregate result projector. Field masking is tightened in D03 production policy integration. */
public final class AggregateResultSecurityProjector implements ResultSecurityProjector<AggregateAgentResultPayload> {
    @Override
    public ContractRef supports() { return AgentExecutionContracts.AGGREGATE_RESULT; }

    @Override
    public Class<AggregateAgentResultPayload> payloadType() { return AggregateAgentResultPayload.class; }

    @Override
    public FilteredResult<AggregateAgentResultPayload> filter(AggregateAgentResultPayload candidate, ExecutionScope scope) {
        return new FilteredResult<>(candidate, "聚合完成", "聚合结果已按当前执行范围过滤");
    }
}
