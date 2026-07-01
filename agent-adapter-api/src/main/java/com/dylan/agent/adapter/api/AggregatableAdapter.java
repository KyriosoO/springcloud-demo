package com.dylan.agent.adapter.api;

import java.util.Set;

import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.api.enums.AggregateFunction;

/** 聚合统计防腐层 SPI。与 QueryableAdapter 独立，首版使用 REPLACE，不做 MERGE。 */
public interface AggregatableAdapter {

    /** 返回稳定、小写、非空的 domain。 */
    String domain();

    /** 返回支持聚合的字段集合。 */
    Set<String> supportedAggregateFields();

    /** 返回指定字段支持的聚合函数集合。 */
    Set<AggregateFunction> supportedFunctions(String field);

    /** 执行聚合查询。 */
    AdapterAggregateResult aggregate(ValidatedAggregateQuery query);
}
