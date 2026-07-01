package com.dylan.agent.capability.query;

import com.dylan.agent.api.response.AgentQueryResult;

/** 包级私有工具类，构建查询成功消息。精确总数返回"找到 N 条记录"，下界估计返回"找到至少 N 条记录"。 */
final class QueryMessages {

    private QueryMessages() {
    }

    static String buildSuccessMessage(AgentQueryResult result) {
        return result.isTotalExact()
                ? "找到 " + result.getTotal() + " 条记录。"
                : "找到至少 " + result.getTotal() + " 条记录。";
    }
}
