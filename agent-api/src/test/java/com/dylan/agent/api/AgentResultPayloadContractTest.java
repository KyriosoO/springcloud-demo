package com.dylan.agent.api;

import com.dylan.agent.api.enums.AgentResponseType;
import com.dylan.agent.api.enums.AgentResultKind;
import com.dylan.agent.api.response.AgentChatResponse;
import com.dylan.agent.api.response.AggregateAgentResultPayload;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class AgentResultPayloadContractTest {

    @Test
    void responseTypeDoesNotExposeAggregateResultBranch() {
        assertThat(AgentResponseType.values())
                .containsExactly(AgentResponseType.RESULT, AgentResponseType.CLARIFY, AgentResponseType.ERROR);
    }

    @Test
    void payloadDiscriminatorsAreFixed() {
        assertThat(new QueryAgentResultPayload().getResultKind()).isEqualTo(AgentResultKind.QUERY);
        assertThat(new AggregateAgentResultPayload().getResultKind()).isEqualTo(AgentResultKind.AGGREGATE);
    }

    @Test
    void chatResponseHasSingleResultSlot() {
        assertThat(AgentChatResponse.class.getDeclaredFields())
                .extracting(java.lang.reflect.Field::getName)
                .contains("result")
                .doesNotContain("queryParameters", "queryResult", "aggregateResult");
    }
}
