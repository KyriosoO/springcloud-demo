package com.dylan.agent.adapter.api;

import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.adapter.api.operation.CapabilityOperationContext;

/** 聚合统计防腐层 SPI。与 QueryableAdapter 独立，首版使用 REPLACE，不做 MERGE。 */
public interface AggregatableAdapter extends AgentAdapterPort {

    /** 执行聚合查询。 */
    AdapterAggregateResult aggregate(
            ValidatedAggregateQuery query,
            CapabilityOperationContext operationContext);
}
