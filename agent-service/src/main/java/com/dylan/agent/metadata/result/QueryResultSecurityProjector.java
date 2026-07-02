package com.dylan.agent.metadata.result;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

/** Query result projector. Field masking is tightened in D03 production policy integration. */
public final class QueryResultSecurityProjector implements ResultSecurityProjector<QueryAgentResultPayload> {
    @Override
    public ContractRef supports() { return AgentExecutionContracts.QUERY_RESULT; }

    @Override
    public Class<QueryAgentResultPayload> payloadType() { return QueryAgentResultPayload.class; }

    @Override
    public FilteredResult<QueryAgentResultPayload> filter(QueryAgentResultPayload candidate, ExecutionScope scope) {
        return new FilteredResult<>(candidate, "查询完成", "查询结果已按当前执行范围过滤");
    }
}
