package com.dylan.agent.lifecycle.model;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.response.AgentQueryParameters;
import com.dylan.agent.api.response.AgentQueryResult;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.InvocationState;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FinalizedInvocationResultTest {

    @Test
    void storedInvocationResultRequiresContractAndPayloadToAppearTogether() {
        assertThatThrownBy(() -> new StoredInvocationResult(
                "result-1",
                new ContractRef("agent.test", "QueryAgentResultPayload", "v1"),
                null,
                "safe message",
                "safe summary"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("together");
    }

    @Test
    void finalizedInvocationResultExposesTypedStoredResult() {
        StoredInvocationResult stored = new StoredInvocationResult(
                "result-1",
                new ContractRef("agent.test", "QueryAgentResultPayload", "v1"),
                queryPayload(),
                "safe message",
                "safe summary");

        FinalizedInvocationResult result = FinalizedInvocationResult.builder()
                .invocationId("inv-1")
                .origin(new ChatInvocationOrigin("conv-1", "turn-1"))
                .state(InvocationState.COMPLETED)
                .responseType(InvocationResponseType.SUCCESS)
                .storedResult(stored)
                .safeMessage("safe message")
                .build();

        assertThat(result.storedResult()).containsSame(stored);
        assertThat(result.storedResult().orElseThrow().payload())
                .containsInstanceOf(QueryAgentResultPayload.class);
    }

    private QueryAgentResultPayload queryPayload() {
        AgentQueryParameters parameters = new AgentQueryParameters();
        parameters.setDomain("employee");
        parameters.setFilters(List.of());
        parameters.setSelectFields(List.of("name"));
        parameters.setPage(1);
        parameters.setSize(20);

        AgentQueryResult queryResult = new AgentQueryResult();
        queryResult.setColumns(List.of("name"));
        queryResult.setRows(List.of(Map.of("name", "Alice")));
        queryResult.setTotal(1);
        queryResult.setTotalExact(true);
        queryResult.setPage(1);
        queryResult.setSize(20);

        return new QueryAgentResultPayload(parameters, queryResult);
    }
}
