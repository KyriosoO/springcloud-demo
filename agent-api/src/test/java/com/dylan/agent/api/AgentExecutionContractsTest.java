package com.dylan.agent.api;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.AgentRuntimeContract;
import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AgentExecutionContractsTest {

    @Test
    void exposesSevenUniqueContractRefs() {
        Set<ContractRef> refs = Set.of(
                AgentExecutionContracts.QUERY_PLAN,
                AgentExecutionContracts.AGGREGATE_PLAN,
                AgentExecutionContracts.QUERY_RESULT,
                AgentExecutionContracts.QUERY_PREVIEW_RESULT,
                AgentExecutionContracts.AGGREGATE_RESULT,
                AgentExecutionContracts.QUERY_CONTEXT,
                AgentExecutionContracts.AGGREGATE_CONTEXT);

        assertThat(refs).hasSize(7);
        assertThat(AgentExecutionContracts.QUERY_PLAN.version())
                .isEqualTo(AgentRuntimeContract.VERSION);
        assertThat(AgentExecutionContracts.AGGREGATE_PLAN.version())
                .isEqualTo(AgentRuntimeContract.VERSION);
        assertThat(AgentExecutionContracts.QUERY_RESULT.version()).isEqualTo("1.1.0");
        assertThat(AgentExecutionContracts.QUERY_PREVIEW_RESULT.version()).isEqualTo("1.1.0");
        assertThat(AgentExecutionContracts.AGGREGATE_RESULT.version()).isEqualTo("1.0.0");
        assertThat(AgentExecutionContracts.QUERY_CONTEXT.version()).isEqualTo("1.2.0");
        assertThat(AgentExecutionContracts.AGGREGATE_CONTEXT.version()).isEqualTo("1.0.0");
    }

    @Test
    void rejectsPointersClassNamesAndImplicitLatest() {
        assertThatThrownBy(() -> new ContractRef("Agent.Execution", "QueryAgentPlan", "1.0.0"))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new ContractRef("agent.execution", "#/components/schemas/QueryAgentPlan", "1.0.0"))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new ContractRef("agent.execution", "QueryAgentPlan", "latest"))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
