package com.dylan.agent.capability.aggregate;

import com.dylan.agent.api.response.AgentAggregateResult;

/** AGGREGATE 结果消息构建。 */
final class AggregateMessages {

    private AggregateMessages() {
    }

    static String success(AgentAggregateResult result) {
        return "聚合结果: " + result.getMetricAliases().size() + " 个指标, "
                + result.getRows().size() + " 行";
    }
}
