package com.dylan.agent.adapter.transaction;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.AdapterAggregateResult;
import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.AggregatableAdapter;
import com.dylan.agent.adapter.api.QueryableAdapter;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.transaction.api.model.AggregateRequest;
import com.dylan.transaction.api.query.TransactionSearchRequest;
import com.dylan.transaction.api.query.TransactionSearchResponse;

import feign.FeignException;

/**
 * Transaction 域适配器，实现 QueryableAdapter 接口。
 * 将 ValidatedQuery 转换为下游 TransactionSearch API 的请求格式，调用 Feign client，
 * 解析响应为 AdapterQueryResult。
 * 负责 Feign 异常到 AgentAdapterException 的转换。
 */
@Component
public class TransactionAgentAdapter implements QueryableAdapter, AggregatableAdapter {

    private static final Logger log = LoggerFactory.getLogger(TransactionAgentAdapter.class);

    private final TransactionPlanMapper planMapper;
    private final TransactionAgentClient client;
    private final TransactionSearchResponseMapper responseMapper;
    private final TransactionAggregateResponseMapper aggregateResponseMapper;

    public TransactionAgentAdapter(TransactionPlanMapper planMapper,
                                    TransactionAgentClient client,
                                    TransactionSearchResponseMapper responseMapper,
                                    TransactionAggregateResponseMapper aggregateResponseMapper) {
        this.planMapper = planMapper;
        this.client = client;
        this.responseMapper = responseMapper;
        this.aggregateResponseMapper = aggregateResponseMapper;
    }

    @Override
    public AdapterQueryResult query(ValidatedQuery query) {
        TransactionSearchRequest request = planMapper.toSearchRequest(query);

        TransactionSearchResponse response;
        try {
            response = client.search(request);
        } catch (FeignException e) {
            log.error("Transaction search Feign error: status={}", e.status());
            throw new AgentAdapterException("Transaction 服务查询失败。", e);
        }

        return responseMapper.toAdapterQueryResult(response, query);
    }

    @Override
    public AdapterAggregateResult aggregate(ValidatedAggregateQuery query) {
        AggregateRequest request = planMapper.toAggregateRequest(query);

        java.util.Map<String, Object> response;
        try {
            response = client.aggregate(request);
        } catch (FeignException e) {
            log.error("Transaction aggregate Feign error: status={}", e.status());
            throw new AgentAdapterException("Transaction 服务聚合失败。", e);
        }

        return aggregateResponseMapper.toAdapterAggregateResult(response, query);
    }
}
