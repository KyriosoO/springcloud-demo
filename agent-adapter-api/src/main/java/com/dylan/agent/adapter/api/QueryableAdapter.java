package com.dylan.agent.adapter.api;

import com.dylan.agent.adapter.api.query.ValidatedQuery;

/** Agent 与业务域之间的防腐层 SPI。Adapter 接收 Java 已验证的 ValidatedQuery，不接收原始 LLM JSON。 */
public interface QueryableAdapter extends AgentAdapterPort {

    /** 执行查询。业务调用身份由当前认证线程 JWT 和 common-security Feign Token Relay 传递。 */
    AdapterQueryResult query(ValidatedQuery query);
}
