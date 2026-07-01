package com.dylan.agent.adapter.employee;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

import com.dylan.esquery.api.model.SearchRequest;

/**
 * Employee 查询服务的 Feign 客户端，封装对下游 employee-search API 的 HTTP 调用。
 * 通过 Spring Cloud OpenFeign 自动生成实现。
 */
@FeignClient(
    name = "employee-service",
    path = "/employees/es",
    contextId = "agent2employee")
public interface EmployeeAgentClient {

    @PostMapping(
        value = "/search",
        consumes = MediaType.APPLICATION_JSON_VALUE,
        produces = MediaType.APPLICATION_JSON_VALUE)
    String search(@RequestBody SearchRequest request);
}
