package com.dylan.agent.adapter.transaction;

import java.util.Map;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

import com.dylan.transaction.api.model.AggregateRequest;
import com.dylan.transaction.api.query.TransactionSearchRequest;
import com.dylan.transaction.api.query.TransactionSearchResponse;

/**
 * Transaction 查询服务的 Feign 客户端，封装对下游 transaction-search API 的 HTTP 调用。
 * 通过 Spring Cloud OpenFeign 自动生成实现，Token 使用 common-security 的 Feign Token relay 透传。
 */
@FeignClient(
    name = "mq-procedure-service",
    path = "/txn",
    contextId = "agent2transaction",
    configuration = TransactionAgentFeignSecurityConfiguration.class)
public interface TransactionAgentClient {

    @PostMapping(
        value = "/search",
        consumes = MediaType.APPLICATION_JSON_VALUE,
        produces = MediaType.APPLICATION_JSON_VALUE)
    TransactionSearchResponse search(@RequestBody TransactionSearchRequest request);

    @PostMapping(
        value = "/aggregate",
        consumes = MediaType.APPLICATION_JSON_VALUE,
        produces = MediaType.APPLICATION_JSON_VALUE)
    Map<String, Object> aggregate(@RequestBody AggregateRequest request);
}
