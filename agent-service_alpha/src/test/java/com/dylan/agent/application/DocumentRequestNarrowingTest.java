package com.dylan.agent.application;

import com.dylan.agent.api.request.AgentChatRequest;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.shared.ref.AgentProfileRef;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentRequestNarrowingTest {
    @Test
    void propagatesCallerDocumentPreferenceWithoutChangingExactProfileRef() {
        AgentProperties properties = new AgentProperties();
        properties.getProfile().setAgentId("agent-default");
        properties.getProfile().setProfileVersion("profile-v1");
        AgentChatRequest request = new AgentChatRequest();
        request.setMessage("查询税务政策");
        request.setRequestedProfile("tax-policy-v3");
        request.setMaterialType("tax_policy");
        Instant deadline = Instant.parse("2026-07-14T08:00:00Z");
        StartChatCommand start = new StartChatCommandFactory(properties).create(
                new AgentUserContext("user-1"), request, deadline);

        AgentProfileRef exact = AgentProfileRef.of("agent-default", "profile-v1");
        assertThat(start.requestedProfile()).isEqualTo("tax-policy-v3");
        assertThat(start.materialType()).isEqualTo("tax_policy");
        assertThat(start.agentProfileRef()).isEqualTo(exact);

        InvocationHandle handle = InvocationHandle.forChat(
                "invocation-1", new ChatInvocationOrigin("conversation-1", "turn-1"), "correlation-1",
                new ExecutionSubjectRef("user", "user-1"),
                new ContextOwnerRef("conversation", "conversation-1"),
                new ConversationScope("conversation-1"), exact, deadline);
        var planning = new PlanningCommandFactory().create(
                handle, start.message(), List.of(), start.requestedProfile(), start.materialType());
        assertThat(planning.requestedProfile()).isEqualTo("tax-policy-v3");
        assertThat(planning.materialType()).isEqualTo("tax_policy");
        assertThat(planning.agentProfileRef()).isEqualTo(exact);
    }
}
