package com.dylan.agent.capability;

import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.api.runtime.RuntimeQueryContext;
import com.dylan.agent.model.AgentUserContext;

/**
 * 传入 {@link AgentCapabilityHandler#validate} 的不可变上下文。
 * 封装 Runtime 原始响应、身份标识和用户上下文，validator 无需反向依赖 orchestrator。
 */
public final class CapabilityValidationContext {

    private final PlanGenerateResponse planResponse;
    private final String expectedRequestId;
    private final RuntimeQueryContext previousQuery;
    private final AgentUserContext userContext;

    public CapabilityValidationContext(
            PlanGenerateResponse planResponse,
            String expectedRequestId,
            RuntimeQueryContext previousQuery,
            AgentUserContext userContext) {
        this.planResponse = planResponse;
        this.expectedRequestId = expectedRequestId;
        this.previousQuery = previousQuery;
        this.userContext = userContext;
    }

    public PlanGenerateResponse planResponse() {
        return planResponse;
    }

    public String expectedRequestId() {
        return expectedRequestId;
    }

    public RuntimeQueryContext previousQuery() {
        return previousQuery;
    }

    public AgentUserContext userContext() {
        return userContext;
    }
}
