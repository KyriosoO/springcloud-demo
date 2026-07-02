package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Clock;
import java.time.ZoneOffset;
import java.util.Map;

import org.junit.jupiter.api.Test;

import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.metadata.authorization.internal.AuthorizationPlanningPortImpl;
import com.dylan.agent.metadata.authorization.internal.DelegationBoundary;
import com.dylan.agent.metadata.authorization.internal.UserPermissionBoundary;
import com.dylan.agent.metadata.authorization.model.DelegationConstraint;
import com.dylan.agent.metadata.authorization.model.DelegationConstraintRef;
import com.dylan.agent.metadata.authorization.request.PlanningSecurityRequest;
import com.dylan.agent.metadata.config.AgentMetadataStore;
import com.dylan.agent.metadata.profile.internal.EffectiveProfileCalculator;
import com.dylan.agent.shared.ref.AgentProfileRef;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

class AuthorizationPlanningPortTest {
    @Test
    void captureIntersectsProfilePolicyPermissionAndDelegation() {
        var port = new AuthorizationPlanningPortImpl(
                new AgentMetadataStore(MetadataTestSupport.bundle("bundle-v1", "digest-v1")),
                new EffectiveProfileCalculator(),
                new UserPermissionBoundary((subject, deadline) -> MetadataTestSupport.permission(subject),
                        Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC)),
                new DelegationBoundary(Map.of(DelegationConstraintRef.CHAT_ALL,
                        new DelegationConstraint(DelegationConstraintRef.CHAT_ALL,
                                java.util.Set.of("query.search"), java.util.Set.of("employee")))),
                DomainMetadataTestSupport.domainMetadataPort(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        var evidence = port.capture(new PlanningSecurityRequest(handle(), handle().agentProfileRef(),
                DelegationConstraintRef.CHAT_ALL));

        assertThat(evidence.planningScope().allowedCapabilityIds()).containsExactly("query.search");
        assertThat(evidence.planningScope().allowedDomains()).containsExactly("employee");
    }

    private InvocationHandle handle() {
        return InvocationHandle.create(
                "inv-1",
                InvocationType.CHAT,
                new ChatInvocationOrigin("conv-1", "turn-1"),
                "corr-1",
                new ExecutionSubjectRef("user", "u-1"),
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                AgentProfileRef.of("agent-default", "profile-v1"),
                MetadataTestSupport.NOW.plusSeconds(60));
    }
}
