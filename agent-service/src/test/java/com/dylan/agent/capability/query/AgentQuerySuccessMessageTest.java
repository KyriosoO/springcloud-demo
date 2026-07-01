package com.dylan.agent.capability.query;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

import com.dylan.agent.api.response.AgentQueryResult;
import com.dylan.agent.capability.query.QueryMessages;

class AgentQuerySuccessMessageTest {

    @Test
    void exactTotalUsesExactMessage() {
        AgentQueryResult result = result(9523, true);

        assertThat(QueryMessages.buildSuccessMessage(result))
                .isEqualTo("找到 9523 条记录。");
    }

    @Test
    void lowerBoundTotalUsesAtLeastMessage() {
        AgentQueryResult result = result(10000, false);

        assertThat(QueryMessages.buildSuccessMessage(result))
                .isEqualTo("找到至少 10000 条记录。");
    }

    private AgentQueryResult result(long total, boolean totalExact) {
        AgentQueryResult result = new AgentQueryResult();
        result.setTotal(total);
        result.setTotalExact(totalExact);
        return result;
    }
}
