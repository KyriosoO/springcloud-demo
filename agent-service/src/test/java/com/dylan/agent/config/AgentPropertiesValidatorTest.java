package com.dylan.agent.config;

import org.junit.jupiter.api.Test;
import java.time.Duration;
import static org.assertj.core.api.Assertions.*;

class AgentPropertiesValidatorTest {
    @Test
    void validatesOnlyTechnicalConfigurationStillOwnedByAgentProperties() {
        AgentProperties properties = valid();
        assertThatCode(() -> new AgentPropertiesValidator(properties).afterPropertiesSet()).doesNotThrowAnyException();

        properties.getDocument().getAcl().setScopeUrl(" ");
        assertThatThrownBy(() -> new AgentPropertiesValidator(properties).afterPropertiesSet())
                .isInstanceOf(IllegalStateException.class).hasMessageContaining("acl.scope-url");
    }

    @Test
    void rejectsMissingAclEndpointBecauseDocumentRegistrationIsNotFeatureFlagged() {
        AgentProperties properties = valid();
        properties.getDocument().getAcl().setScopeUrl(null);
        assertThatThrownBy(() -> new AgentPropertiesValidator(properties).afterPropertiesSet())
                .isInstanceOf(IllegalStateException.class).hasMessageContaining("acl.scope-url");
    }

    private static AgentProperties valid() {
        AgentProperties value = new AgentProperties();
        value.getProfile().setAllowedDomains(java.util.Set.of("employee"));
        AgentProperties.RuntimeProperties runtime = new AgentProperties.RuntimeProperties();
        runtime.setBaseUrl("http://agent-runtime"); runtime.setSharedKey("0123456789abcdef");
        runtime.setConnectTimeout(Duration.ofSeconds(1)); runtime.setReadTimeout(Duration.ofSeconds(2));
        runtime.setMaxResponseBytes(1024); value.setRuntime(runtime);
        AgentProperties.QueryProperties query = new AgentProperties.QueryProperties();
        query.setDefaultSize(10); query.setMaxSize(20); query.setMaxResultWindow(100);
        query.setMaxFilters(5); query.setMaxInValues(10); query.setMaxFilterValueLength(64);
        query.setMaxDownstreamResponseBytes(1024); value.setQuery(query);
        value.setAggregate(new AgentProperties.AggregateProperties());
        AgentProperties.ConversationProperties conversation = new AgentProperties.ConversationProperties();
        conversation.setRecentTurnLimit(5); conversation.setRetentionDays(7); conversation.setCleanupDelay(Duration.ofMinutes(1));
        value.setConversation(conversation);
        value.getDocument().getAcl().setScopeUrl("http://auth-service");
        return value;
    }
}
