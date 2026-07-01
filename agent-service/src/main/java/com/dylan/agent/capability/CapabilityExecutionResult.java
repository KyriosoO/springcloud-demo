package com.dylan.agent.capability;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentResponseType;
import com.dylan.agent.api.response.AggregateAgentResultPayload;
import com.dylan.agent.api.response.AgentAggregateResult;
import com.dylan.agent.api.response.AgentChatResponse;
import com.dylan.agent.api.response.AgentQueryParameters;
import com.dylan.agent.api.response.AgentQueryResult;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.api.runtime.RuntimeQueryContext;

/**
 * 统一的执行结果，由每个 {@link AgentCapabilityHandler} 返回。
 *
 * <p>本类型仅表达成功。失败走 {@code AgentException → conversationService.completeFailure()}
 * 异常链路，因此 {@code applyTo} 硬编码 {@code errorCode = null}。
 *
 * <p>工厂方法封装了正确的 intent / responseType 组合：
 * {@link #queryResult} → QUERY + RESULT，
 * {@link #clarify} → CLARIFY + CLARIFY，
     * {@link #aggregateResult} → AGGREGATE + RESULT。
 */
public final class CapabilityExecutionResult {

    private final AgentIntent intent;
    private final AgentResponseType responseType;
    private final String assistantMessage;
    private final AgentQueryParameters queryParameters;
    private final AgentQueryResult queryResult;
    private final AgentAggregateResult aggregateResult;
    private final Object contextToPersist;

    private CapabilityExecutionResult(
            AgentIntent intent,
            AgentResponseType responseType,
            String assistantMessage,
            AgentQueryParameters queryParameters,
            AgentQueryResult queryResult,
            AgentAggregateResult aggregateResult,
            Object contextToPersist) {
        this.intent = intent;
        this.responseType = responseType;
        this.assistantMessage = assistantMessage;
        this.queryParameters = queryParameters;
        this.queryResult = queryResult;
        this.aggregateResult = aggregateResult;
        this.contextToPersist = contextToPersist;
    }

    public static CapabilityExecutionResult queryResult(
            String assistantMessage,
            AgentQueryParameters queryParameters,
            AgentQueryResult queryResult,
            RuntimeQueryContext queryContextToPersist) {
        return new CapabilityExecutionResult(
                AgentIntent.QUERY,
                AgentResponseType.RESULT,
                assistantMessage,
                queryParameters,
                queryResult,
                null,
                queryContextToPersist);
    }

    public static CapabilityExecutionResult clarify(String question) {
        return new CapabilityExecutionResult(
                AgentIntent.CLARIFY,
                AgentResponseType.CLARIFY,
                question,
                null,
                null,
                null,
                null);
    }

    public static CapabilityExecutionResult aggregateResult(
            String assistantMessage,
            AgentAggregateResult aggregateResult,
            Object contextToPersist) {
        return new CapabilityExecutionResult(
                AgentIntent.AGGREGATE,
                AgentResponseType.RESULT,
                assistantMessage,
                null,
                null,
                aggregateResult,
                contextToPersist);
    }

    public AgentIntent intent() {
        return intent;
    }

    public AgentResponseType responseType() {
        return responseType;
    }

    public String assistantMessage() {
        return assistantMessage;
    }

    public AgentQueryParameters queryParameters() {
        return queryParameters;
    }

    public AgentQueryResult queryResult() {
        return queryResult;
    }

    public AgentAggregateResult aggregateResult() {
        return aggregateResult;
    }

    /** 非 null 时触发持久化 query_context_json。类型由调用方 Handler 决定（QUERY → RuntimeQueryContext，AGGREGATE → RuntimeAggregateContext）。 */
    public Object contextToPersist() {
        return contextToPersist;
    }

    /**
     * 将结果字段装配到响应 DTO。errorCode 设为 null 因为错误走异常链路。
     */
    public void applyTo(AgentChatResponse response) {
        response.setType(responseType);
        response.setMessage(assistantMessage);
        response.setSummary(assistantMessage);
        if (queryParameters != null || queryResult != null) {
            response.setResult(new QueryAgentResultPayload(queryParameters, queryResult));
        } else if (aggregateResult != null) {
            response.setResult(new AggregateAgentResultPayload(aggregateResult));
        } else {
            response.setResult(null);
        }
        response.setErrorCode(null);
    }
}
