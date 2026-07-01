package com.dylan.agent.config;

import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.capability.AgentCapabilityHandler;
import com.dylan.agent.capability.AgentCapabilityHandlerRegistry;
import com.dylan.agent.capability.CapabilityExecutionContext;
import com.dylan.agent.capability.CapabilityExecutionResult;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.capability.model.ValidatedCapabilityPlan;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@DisplayName("AgentPropertiesValidator")
class AgentPropertiesValidatorTest {

    private AgentProperties properties;
    private AgentCapabilityHandlerRegistry handlerRegistry;

    @BeforeEach
    void setUp() {
        properties = DomainMetadataTestSupport.agentProperties();
        handlerRegistry = new AgentCapabilityHandlerRegistry(List.of(
                new TestCapabilityHandler(AgentIntent.QUERY),
                new TestCapabilityHandler(AgentIntent.CLARIFY),
                new TestCapabilityHandler(AgentIntent.AGGREGATE)));
    }

    @Nested
    @DisplayName("启动成功场景")
    class ValidScenarios {
        @Test
        @DisplayName("完整合法运行配置不抛异常")
        void shouldPassWithValidConfig() {
            var validator = new AgentPropertiesValidator(properties, handlerRegistry);
            assertThatCode(validator::afterPropertiesSet).doesNotThrowAnyException();
        }
    }

    @Nested
    @DisplayName("运行配置校验")
    class RuntimeValidation {
        @Test
        @DisplayName("defaultSize > maxSize 时启动失败")
        void shouldFailWhenDefaultAboveMax() {
            properties.getQuery().setDefaultSize(200);
            properties.getQuery().setMaxSize(100);
            var validator = new AgentPropertiesValidator(properties, handlerRegistry);
            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("default-size");
        }

        @Test
        @DisplayName("shared-key 不足 16 字符时启动失败")
        void shouldFailWhenSharedKeyTooShort() {
            properties.getRuntime().setSharedKey("short");
            var validator = new AgentPropertiesValidator(properties, handlerRegistry);
            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("shared-key");
        }

        @Test
        @DisplayName("缺少 intent handler 时启动失败")
        void shouldFailWhenHandlerMissing() {
            handlerRegistry = new AgentCapabilityHandlerRegistry(List.of(
                    new TestCapabilityHandler(AgentIntent.QUERY),
                    new TestCapabilityHandler(AgentIntent.CLARIFY)));
            var validator = new AgentPropertiesValidator(properties, handlerRegistry);
            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("AGGREGATE");
        }

        @Test
        @DisplayName("缺少 intent-roles 时启动失败")
        void shouldFailWhenIntentRolesMissing() {
            properties.setIntentRoles(Map.of(
                    AgentIntent.QUERY, Set.of("agent:viewer"),
                    AgentIntent.CLARIFY, Set.of("agent:viewer")));
            var validator = new AgentPropertiesValidator(properties, handlerRegistry);
            assertThatThrownBy(validator::afterPropertiesSet)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("AGGREGATE");
        }
    }

    private static final class TestCapabilityHandler implements AgentCapabilityHandler<ValidatedCapabilityPlan> {
        private final AgentIntent intent;

        TestCapabilityHandler(AgentIntent intent) {
            this.intent = intent;
        }

        @Override
        public AgentIntent intent() { return intent; }

        @Override
        public AgentCapabilityRiskLevel riskLevel() { return AgentCapabilityRiskLevel.READ_ONLY; }

        @Override
        public ValidatedCapabilityPlan validate(CapabilityValidationContext context) { return null; }

        @Override
        public CapabilityExecutionResult execute(CapabilityExecutionContext context, ValidatedCapabilityPlan plan) {
            return null;
        }
    }
}
