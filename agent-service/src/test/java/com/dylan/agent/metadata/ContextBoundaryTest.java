package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Clock;
import java.time.ZoneOffset;
import java.util.List;

import org.junit.jupiter.api.Test;

import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.kernel.port.model.ContextApprovalRequest;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.context.internal.ContextBoundary;
import com.dylan.agent.metadata.context.model.ContextWriteCandidate;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.shared.ref.AgentProfileRef;

class ContextBoundaryTest {
    @Test
    void approveDerivesOwnerScopeAndExpectedAbsentInsteadOfTrustingHandler() {
        ContextBoundary boundary = new ContextBoundary(
                new NoopContextRepository(), new PayloadJsonCodec(), new PlainCodec(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        var approved = boundary.approve(
                List.of(new ContextWriteCandidate(RuntimeContextType.QUERY,
                        com.dylan.agent.api.contract.common.AgentExecutionContracts.QUERY_CONTEXT,
                        new com.dylan.agent.api.context.QueryCapabilityContextPayload(List.of(), List.of("name"), 1, 10))),
                new ContextApprovalRequest(handle(), nullRegistration(), executionScope(), List.of(), MetadataTestSupport.NOW));

        assertThat(approved).singleElement().satisfies(write -> {
            assertThat(write.recordKey().owner().id()).isEqualTo("conv-1");
            assertThat(write.expectedVersion().expectsAbsent()).isTrue();
        });
    }

    private InvocationHandle handle() {
        return InvocationHandle.create("inv-1", InvocationType.CHAT,
                new ChatInvocationOrigin("conv-1", "turn-1"), "corr",
                new ExecutionSubjectRef("user", "u-1"), new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"), AgentProfileRef.of("agent-default", "profile-v1"),
                MetadataTestSupport.NOW.plusSeconds(60));
    }

    private ExecutionScope executionScope() {
        return new ExecutionScope("user:u-1",
                new com.dylan.agent.metadata.domain.port.DomainMetadataEvidence("catalog", "adapter", "availability", MetadataTestSupport.NOW),
                MetadataTestSupport.NOW, "perm", "perm-v1", "policy-v1",
                java.util.Set.of("query.search"), java.util.Set.of("employee"),
                java.util.Map.of(), java.util.Map.of(), java.time.Duration.ofSeconds(30), 1, 100, 10_000);
    }

    private com.dylan.agent.kernel.registration.ResolvedRegistration nullRegistration() {
        return com.dylan.agent.testsupport.KernelTestSupport.resolvedQueryRegistration();
    }
}
