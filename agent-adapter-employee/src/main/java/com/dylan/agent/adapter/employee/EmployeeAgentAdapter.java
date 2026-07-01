package com.dylan.agent.adapter.employee;

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
import com.dylan.esquery.api.model.SearchRequest;

import feign.FeignException;

/**
 * Employee 域适配器，实现 QueryableAdapter 接口。
 * 将 ValidatedQuery 转换为下游 EmployeeSearch API 的请求格式，调用 Feign client，
 * 解析响应为 AdapterQueryResult。
 * 负责 Feign 异常到 AgentAdapterException 的转换。
 */
@Component
public class EmployeeAgentAdapter implements QueryableAdapter, AggregatableAdapter {

    private static final Logger log = LoggerFactory.getLogger(EmployeeAgentAdapter.class);

    private final EmployeePlanMapper planMapper;
    private final EmployeeAgentClient employeeClient;
    private final EmployeeSearchResponseParser parser;
    private final EmployeeAdapterProperties adapterProperties;

    public EmployeeAgentAdapter(EmployeePlanMapper planMapper, EmployeeAgentClient employeeClient,
                                EmployeeSearchResponseParser parser, EmployeeAdapterProperties adapterProperties) {
        this.planMapper = planMapper;
        this.employeeClient = employeeClient;
        this.parser = parser;
        this.adapterProperties = adapterProperties;
    }

    @Override
    public AdapterQueryResult query(ValidatedQuery query) {
        SearchRequest request = planMapper.toSearchRequest(query);

        String rawResponse;
        try {
            rawResponse = employeeClient.search(request);
        } catch (FeignException e) {
            log.error("Employee search Feign error: status={}", e.status());
            throw new AgentAdapterException("Employee 服务查询失败。", e);
        }

        return parser.parse(rawResponse, query.getPage(), query.getSize(),
                adapterProperties.getMaxResponseBytes());
    }

    @Override
    public AdapterAggregateResult aggregate(ValidatedAggregateQuery query) {
        SearchRequest request = planMapper.toAggregateSearchRequest(query);

        String rawResponse;
        try {
            rawResponse = employeeClient.search(request);
        } catch (FeignException e) {
            log.error("Employee aggregate Feign error: status={}", e.status());
            throw new AgentAdapterException("Employee 服务聚合失败。", e);
        }

        return parser.parseAggregate(rawResponse, query, adapterProperties.getMaxResponseBytes());
    }
}
