package com.dylan.agent.adapter.api;

import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.adapter.api.operation.CapabilityOperationContext;

/** Agent 与业务域之间的防腐层 SPI。Adapter 接收 Java 已验证的 ValidatedQuery，不接收原始 LLM JSON。 */
public interface QueryableAdapter extends AgentAdapterPort {

    /** 使用显式 operation context 执行查询，不依赖调用线程中的用户 JWT。 */
    AdapterQueryResult query(ValidatedQuery query, CapabilityOperationContext operationContext);
}
