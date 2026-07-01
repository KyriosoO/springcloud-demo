package com.dylan.agent.adapter.transaction;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.transaction.api.model.Transaction;
import com.dylan.transaction.api.query.TransactionSearchResponse;

/**
 * 解析下游 TransactionSearch API 响应，包装为 AdapterQueryResult。
 * 处理总数估计标记（isTotalExact）的传递、页号与 size 一致性校验，以及业务字段的类型转换。
 * 只输出 transId/transType/transDate/amount 四个字段，查询辅助字段不进入 row。
 */
@Component
public class TransactionSearchResponseMapper {

    /** 解析下游 TransactionSearch API 响应，包装为 AdapterQueryResult。处理总数估计标记和页号规范化。 */
    public AdapterQueryResult toAdapterQueryResult(
            TransactionSearchResponse response,
            ValidatedQuery query) {

        if (response == null) {
            throw new AgentAdapterException("Transaction 搜索响应为空。");
        }
        if (response.getRows() == null) {
            throw new AgentAdapterException("Transaction 搜索响应 rows 为空。");
        }
        if (response.getTotal() < 0) {
            throw new AgentAdapterException("Transaction 搜索 total 不能为负。");
        }
        if (response.getPage() != query.getPage() || response.getSize() != query.getSize()) {
            throw new AgentAdapterException("Transaction 响应 page/size 与请求不一致。");
        }
        if (response.getRows().size() > query.getSize()) {
            throw new AgentAdapterException("Transaction 返回行数超出请求 size。");
        }
        if (response.getRows().stream().anyMatch(java.util.Objects::isNull)) {
            throw new AgentAdapterException("Transaction 搜索响应包含空 row。");
        }

        List<Map<String, Object>> rows = response.getRows().stream()
                .map(TransactionSearchResponseMapper::toRow)
                .toList();

        return new AdapterQueryResult(rows, response.getTotal(), response.isTotalExact(),
                response.getPage(), response.getSize());
    }

    static Map<String, Object> toRow(Transaction transaction) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("transId", transaction.getTransId());
        row.put("transType", transaction.getTransType());
        row.put("transDate", transaction.getTransDate() == null
                ? null
                : transaction.getTransDate().toInstant().toString());
        row.put("amount", transaction.getAmount());
        return row;
    }
}
