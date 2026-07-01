package com.dylan.agent.capability;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.capability.model.ValidatedCapabilityPlan;
import com.dylan.agent.exception.AgentPlanValidationException;

@DisplayName("CapabilityRouter")
class CapabilityRouterTest {

    private CapabilityRouter router;

    @BeforeEach
    void setUp() {
        var query = new TestHandler(AgentIntent.QUERY);
        var clarify = new TestHandler(AgentIntent.CLARIFY);
        var registry = new AgentCapabilityHandlerRegistry(List.of(query, clarify));
        router = new CapabilityRouter(registry);
    }

    @Test
    @DisplayName("null intent 拒绝")
    void shouldRejectNullIntent() {
        assertThatThrownBy(() -> router.route(null))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("intent 为空");
    }

    @Test
    @DisplayName("QUERY 返回 handler")
    void shouldReturnQueryHandler() {
        AgentCapabilityHandler<?> handler = router.route(AgentIntent.QUERY);
        assertThat(handler.intent()).isEqualTo(AgentIntent.QUERY);
    }

    @Test
    @DisplayName("CLARIFY 返回 handler")
    void shouldReturnClarifyHandler() {
        AgentCapabilityHandler<?> handler = router.route(AgentIntent.CLARIFY);
        assertThat(handler.intent()).isEqualTo(AgentIntent.CLARIFY);
    }

    @Test
    @DisplayName("未注册 intent 拒绝")
    void shouldRejectUnregisteredIntent() {
        var registry = new AgentCapabilityHandlerRegistry(List.of(
                new TestHandler(AgentIntent.QUERY)));
        var sparseRouter = new CapabilityRouter(registry);

        assertThatThrownBy(() -> sparseRouter.route(AgentIntent.CLARIFY))
                .isInstanceOf(AgentPlanValidationException.class)
                .hasMessageContaining("不支持的 Agent intent");
    }

    private static final class TestHandler implements AgentCapabilityHandler<ValidatedCapabilityPlan> {
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
        public ValidatedCapabilityPlan validate(CapabilityValidationContext context) {
            return null;
        }

        @Override
        public CapabilityExecutionResult execute(CapabilityExecutionContext context,
                                                  ValidatedCapabilityPlan plan) {
            return null;
        }
    }
}
