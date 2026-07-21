package com.dylan.agent.api.contract.common;

import com.dylan.agent.api.contract.runtime.common.AgentRuntimeContract;

/**
 * capability registration 共享消费的 Java 契约引用。
 */
public final class AgentExecutionContracts {

    public static final String NAMESPACE = "agent.execution";

    public static final ContractRef QUERY_PLAN =
            ref("QueryAgentPlan", AgentRuntimeContract.VERSION);
    public static final ContractRef AGGREGATE_PLAN =
            ref("AggregateAgentPlan", AgentRuntimeContract.VERSION);
    public static final ContractRef DOCUMENT_PLAN =
            ref("DocumentAgentPlan", AgentRuntimeContract.VERSION);
    public static final ContractRef QUERY_RESULT =
            ref("QueryAgentResultPayload", "1.1.0");
    public static final ContractRef QUERY_PREVIEW_RESULT =
            ref("QueryPreviewResultPayload", "1.1.0");
    public static final ContractRef AGGREGATE_RESULT =
            ref("AggregateAgentResultPayload", "1.0.0");
    public static final ContractRef DOCUMENT_RESULT =
            ref("DocumentAgentResultPayload", "1.0.0");
    public static final ContractRef QUERY_CONTEXT =
            ref("QueryCapabilityContextPayload", "1.2.0");
    public static final ContractRef AGGREGATE_CONTEXT =
            ref("AggregateCapabilityContextPayload", "1.0.0");
    public static final ContractRef DOCUMENT_CONTEXT =
            ref("DocumentCapabilityContextPayload", "1.0.0");
    public static final ContractRef STANDARD_RESOURCE_LIMIT =
            ref("StandardCapabilityResourceLimit", "1.0.0");
    public static final ContractRef DOCUMENT_RESOURCE_LIMIT =
            ref("DocumentResourceLimit", "1.0.0");

    public static ContractRef ref(String name, String version) {
        return new ContractRef(NAMESPACE, name, version);
    }

    private AgentExecutionContracts() {
    }
}
