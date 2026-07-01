package com.dylan.agent.capability;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.capability.model.ValidatedCapabilityPlan;

@DisplayName("CapabilityRouter (AGGREGATE)")
class CapabilityRouterAggregateTest {

    private CapabilityRouter router;

    @BeforeEach
    void setUp() {
        var handlerRegistry = new AgentCapabilityHandlerRegistry(List.of(
                new StubHandler(AgentIntent.QUERY),
                new StubHandler(AgentIntent.CLARIFY),
                new StubHandler(AgentIntent.AGGREGATE)));
        router = new CapabilityRouter(handlerRegistry);
    }

    @Test
    @DisplayName("registry 可注册 AGGREGATE handler")
    void shouldRegisterAggregateHandler() {
        var handler = router.route(AgentIntent.AGGREGATE);
        assertThat(handler.intent()).isEqualTo(AgentIntent.AGGREGATE);
    }

    @Test
    @DisplayName("router 仍可路由 QUERY")
    void shouldStillRouteQuery() {
        assertThat(router.route(AgentIntent.QUERY).intent()).isEqualTo(AgentIntent.QUERY);
    }

    @Test
    @DisplayName("router 仍可路由 CLARIFY")
    void shouldStillRouteClarify() {
        assertThat(router.route(AgentIntent.CLARIFY).intent()).isEqualTo(AgentIntent.CLARIFY);
    }

    private record StubHandler(AgentIntent intent)
            implements AgentCapabilityHandler<ValidatedCapabilityPlan> {
        @Override
        public AgentCapabilityRiskLevel riskLevel() {
            return AgentCapabilityRiskLevel.READ_ONLY;
        }

        @Override
        public ValidatedCapabilityPlan validate(CapabilityValidationContext context) {
            throw new UnsupportedOperationException("route-only test");
        }

        @Override
        public CapabilityExecutionResult execute(
                CapabilityExecutionContext context,
                ValidatedCapabilityPlan plan) {
            throw new UnsupportedOperationException("route-only test");
        }
    }
}
