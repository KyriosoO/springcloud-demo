package com.dylan.agent.api.contract.common;

import com.dylan.agent.api.contract.runtime.common.AgentRuntimeContract;

/**
 * capability registration 共享消费的 Java 契约引用。
 */
public final class AgentExecutionContracts {

    public static final ContractRef QUERY_PLAN =
            new ContractRef("QueryAgentPlan", AgentRuntimeContract.VERSION);
    public static final ContractRef AGGREGATE_PLAN =
            new ContractRef("AggregateAgentPlan", AgentRuntimeContract.VERSION);
    public static final ContractRef DOCUMENT_PLAN =
            new ContractRef("DocumentAgentPlan", AgentRuntimeContract.VERSION);
    public static final ContractRef QUERY_RESULT =
            new ContractRef("QueryAgentResultPayload", "1.1.0");
    public static final ContractRef QUERY_PREVIEW_RESULT =
            new ContractRef("QueryPreviewResultPayload", "1.1.0");
    public static final ContractRef AGGREGATE_RESULT =
            new ContractRef("AggregateAgentResultPayload", "1.0.0");
    public static final ContractRef DOCUMENT_RESULT =
            new ContractRef("DocumentAgentResultPayload", "1.0.0");
    public static final ContractRef QUERY_CONTEXT =
            new ContractRef("QueryCapabilityContextPayload", "1.2.0");
    public static final ContractRef AGGREGATE_CONTEXT =
            new ContractRef("AggregateCapabilityContextPayload", "1.0.0");
    public static final ContractRef DOCUMENT_CONTEXT =
            new ContractRef("DocumentCapabilityContextPayload", "1.0.0");

    private AgentExecutionContracts() {
    }
}
