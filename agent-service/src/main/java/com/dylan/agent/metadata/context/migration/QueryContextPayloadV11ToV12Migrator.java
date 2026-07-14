package com.dylan.agent.metadata.context.migration;

import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;

/** QUERY_CONTEXT 1.1.0 到 1.2.0 的精确迁移。 */
public final class QueryContextPayloadV11ToV12Migrator
        implements ContextPayloadMigrator<QueryCapabilityContextPayload, QueryCapabilityContextPayload> {

    private static final ContractRef SOURCE = AgentExecutionContracts.ref("QueryCapabilityContextPayload", "1.1.0");

    @Override
    public ContractRef source() { return SOURCE; }

    @Override
    public Class<QueryCapabilityContextPayload> sourceType() { return QueryCapabilityContextPayload.class; }

    @Override
    public ContractRef target() { return AgentExecutionContracts.QUERY_CONTEXT; }

    @Override
    public Class<QueryCapabilityContextPayload> targetType() { return QueryCapabilityContextPayload.class; }

    @Override
    public QueryCapabilityContextPayload migrate(QueryCapabilityContextPayload sourcePayload) {
        return new QueryCapabilityContextPayload(
                sourcePayload.filters(),
                sourcePayload.selectFields(),
                sourcePayload.sorts(),
                sourcePayload.page(),
                sourcePayload.size(),
                sourcePayload.total(),
                sourcePayload.totalExact(),
                sourcePayload.totalPages());
    }
}
