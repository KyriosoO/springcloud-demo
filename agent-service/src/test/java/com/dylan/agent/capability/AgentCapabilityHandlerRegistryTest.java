package com.dylan.agent.capability;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.Set;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.exception.AgentPlanValidationException;

@DisplayName("AgentCapabilityHandlerRegistry")
class AgentCapabilityHandlerRegistryTest {

    @Test
    @DisplayName("注册 QUERY/CLARIFY 成功")
    void shouldRegisterQueryAndClarify() {
        var query = new TestHandler(AgentIntent.QUERY);
        var clarify = new TestHandler(AgentIntent.CLARIFY);

        var registry = new AgentCapabilityHandlerRegistry(List.of(query, clarify));

        assertThat(registry.supportedIntents())
                .containsExactlyInAnyOrder(AgentIntent.QUERY, AgentIntent.CLARIFY);
    }

    @Test
    @DisplayName("空 handler list 拒绝")
    void shouldRejectEmptyList() {
        assertThatThrownBy(() -> new AgentCapabilityHandlerRegistry(List.of()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("至少需要一个");
    }

    @Test
    @DisplayName("handler intent null 拒绝")
    void shouldRejectNullIntent() {
        var bad = new TestHandler(null);

        assertThatThrownBy(() -> new AgentCapabilityHandlerRegistry(List.of(bad)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("intent must not be null");
    }

    @Test
    @DisplayName("重复 intent 拒绝")
    void shouldRejectDuplicateIntent() {
        var q1 = new TestHandler(AgentIntent.QUERY);
        var q2 = new TestHandler(AgentIntent.QUERY);

        assertThatThrownBy(() -> new AgentCapabilityHandlerRegistry(List.of(q1, q2)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Duplicate");
    }

    @Test
    @DisplayName("unsupported intent getRequired 拒绝")
    void shouldRejectUnsupportedIntent() {
        var query = new TestHandler(AgentIntent.QUERY);
        var registry = new AgentCapabilityHandlerRegistry(List.of(query));

        assertThatThrownBy(() -> registry.getRequired(AgentIntent.CLARIFY))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("不支持的 Agent intent");
    }

    @Test
    @DisplayName("getRequired 返回对应 handler")
    void shouldReturnCorrectHandler() {
        var query = new TestHandler(AgentIntent.QUERY);
        var clarify = new TestHandler(AgentIntent.CLARIFY);
        var registry = new AgentCapabilityHandlerRegistry(List.of(query, clarify));

        assertThat(registry.getRequired(AgentIntent.QUERY)).isSameAs(query);
        assertThat(registry.getRequired(AgentIntent.CLARIFY)).isSameAs(clarify);
    }

    private static final class TestHandler implements AgentCapabilityHandler<com.dylan.agent.capability.model.ValidatedCapabilityPlan> {
        private final AgentIntent intent;

        TestHandler(AgentIntent intent) {
            this.intent = intent;
        }

        @Override
        public AgentIntent intent() {
            return intent;
        }

        @Override
        public com.dylan.agent.api.capability.AgentCapabilityRiskLevel riskLevel() {
            return com.dylan.agent.api.capability.AgentCapabilityRiskLevel.READ_ONLY;
        }

        @Override
        public com.dylan.agent.capability.model.ValidatedCapabilityPlan validate(CapabilityValidationContext context) {
            return null;
        }

        @Override
        public CapabilityExecutionResult execute(CapabilityExecutionContext context,
                                                  com.dylan.agent.capability.model.ValidatedCapabilityPlan plan) {
            return null;
        }
    }
}
