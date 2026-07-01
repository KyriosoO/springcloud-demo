package com.dylan.agent.api.request;

import java.util.List;

import com.dylan.agent.api.capability.AgentCapabilityDescriptor;
import com.dylan.agent.api.runtime.RuntimeDomainSchema;
import com.dylan.agent.api.runtime.RuntimeQueryContext;
import com.dylan.agent.api.runtime.RuntimeTurn;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

/** 发送给 Runtime 的 plan 生成请求，包含用户消息、最近对话轮次、上轮查询上下文和域 schema。 */
@Schema(description = "发送给 Runtime 的 plan 生成请求")
public class PlanGenerateRequest {

    @Schema(description = "请求 ID", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String requestId;

    @Schema(description = "用户消息文本", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String message;

    @Schema(description = "最近对话轮次（最多 6 轮）", nullable = true)
    @Size(max = 6)
    private List<RuntimeTurn> recentTurns;

    @Schema(description = "上轮成功查询的上下文，用于 MERGE 判断", nullable = true)
    private RuntimeQueryContext previousQuery;

    @Schema(description = "领域 schema 列表", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Size(min = 1)
    private List<RuntimeDomainSchema> domainSchemas;

    @Schema(description = "当前请求可用的 Agent capability 列表", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private List<@Valid AgentCapabilityDescriptor> capabilities;

    public PlanGenerateRequest() {
    }

    public String getRequestId() { return requestId; }
    public void setRequestId(String requestId) { this.requestId = requestId; }
    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
    public List<RuntimeTurn> getRecentTurns() { return recentTurns; }
    public void setRecentTurns(List<RuntimeTurn> recentTurns) { this.recentTurns = recentTurns; }
    public RuntimeQueryContext getPreviousQuery() { return previousQuery; }
    public void setPreviousQuery(RuntimeQueryContext previousQuery) { this.previousQuery = previousQuery; }
    public List<RuntimeDomainSchema> getDomainSchemas() { return domainSchemas; }
    public void setDomainSchemas(List<RuntimeDomainSchema> domainSchemas) { this.domainSchemas = domainSchemas; }
    public List<AgentCapabilityDescriptor> getCapabilities() { return capabilities; }
    public void setCapabilities(List<AgentCapabilityDescriptor> capabilities) { this.capabilities = capabilities; }
}
