package com.dylan.agent.adapter.transaction;

import java.util.Set;

/**
 * Transaction 域字段目录，提供 supportedFields() 所用字段集合。
 * 表示 /txn/search 支持的查询字段白名单，权限事实来源仍为 AgentProperties 配置。
 */
public final class TransactionFieldCatalog {

    private static final Set<String> SUPPORTED = Set.of(
            "transId", "transType", "transDate", "amount");

    private TransactionFieldCatalog() {}

    public static Set<String> supportedFields() {
        return SUPPORTED;
    }
}
