package com.dylan.agent.config;

import com.dylan.agent.testsupport.DomainMetadataTestSupport;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@DisplayName("AgentPropertiesValidator")
class AgentPropertiesValidatorTest {

    private AgentProperties properties;

    @BeforeEach
    void setUp() {
        properties = DomainMetadataTestSupport.agentProperties();
    }

    @Test
    @DisplayName("完整合法运行配置不抛异常")
    void shouldPassWithValidConfig() {
        var validator = new AgentPropertiesValidator(properties);

        assertThatCode(validator::afterPropertiesSet).doesNotThrowAnyException();
    }

    @Test
    @DisplayName("defaultSize > maxSize 时启动失败")
    void shouldFailWhenDefaultAboveMax() {
        properties.getQuery().setDefaultSize(200);
        properties.getQuery().setMaxSize(100);
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("default-size");
    }

    @Test
    @DisplayName("shared-key 不足 16 字符时启动失败")
    void shouldFailWhenSharedKeyTooShort() {
        properties.getRuntime().setSharedKey("short");
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("shared-key");
    }

    @Test
    @DisplayName("route/plan path 缺失时启动失败")
    void shouldFailWhenRuntimePlanPathMissing() {
        properties.getRuntime().setPlanPath("");
        var validator = new AgentPropertiesValidator(properties);

        assertThatThrownBy(validator::afterPropertiesSet)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("route-path/plan-path");
    }
}
