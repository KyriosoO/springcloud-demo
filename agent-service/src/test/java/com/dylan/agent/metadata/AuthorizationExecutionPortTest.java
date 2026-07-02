package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Clock;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.Test;

import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.metadata.authorization.internal.AuthorizationExecutionPortImpl;
import com.dylan.agent.metadata.authorization.internal.UserPermissionBoundary;
import com.dylan.agent.metadata.authorization.model.AuthorizationSnapshot;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.shared.ref.AgentProfileRef;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

class AuthorizationExecutionPortTest {
    @Test
    void recheckNeverExpandsSnapshot() {
        AuthorizationExecutionPortImpl port = new AuthorizationExecutionPortImpl(
                new UserPermissionBoundary((subject, deadline) -> MetadataTestSupport.permission(subject),
                        Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC)),
                DomainMetadataTestSupport.domainMetadataPort(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));
        var scope = port.recheck(snapshot(), handle());

        assertThat(scope.allowedCapabilityIds()).containsExactly("query.search");
        assertThat(scope.allowedDomains()).containsExactly("employee");
    }

    private AuthorizationSnapshot snapshot() {
        DomainMetadataEvidence evidence = DomainMetadataTestSupport.store().current().evidence();
        return new AuthorizationSnapshot(
                "auth-1", "user:u-1", "profile-v1", "policy-v1",
                Set.of("query.search"), Set.of("employee"),
                Map.of("employee", Set.of("chineseName")),
                MetadataTestSupport.NOW, evidence);
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
