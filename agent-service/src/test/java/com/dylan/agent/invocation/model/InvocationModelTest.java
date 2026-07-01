package com.dylan.agent.invocation.model;

import com.dylan.agent.shared.ref.AgentProfileRef;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class InvocationModelTest {

    private static final Clock CLOCK =
            Clock.fixed(Instant.parse("2026-07-01T00:00:00Z"), ZoneOffset.UTC);

    @Test
    void handleRequiresCompatibleTypeOriginAndScope() {
        InvocationHandle chat = chatHandle(
                InvocationType.CHAT,
                new ChatInvocationOrigin("conv-1", "turn-1"),
                new ConversationScope("conv-1"));

        assertThat(chat.origin()).isInstanceOf(ChatInvocationOrigin.class);
        assertThat(chat.scope()).isInstanceOf(ConversationScope.class);

        assertThatThrownBy(() -> chatHandle(
                InvocationType.TASK,
                new ChatInvocationOrigin("conv-1", "turn-1"),
                new ConversationScope("conv-1")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("origin");

        assertThatThrownBy(() -> chatHandle(
                InvocationType.CHAT,
                new ChatInvocationOrigin("conv-1", "turn-1"),
                new RunScope("run-1")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("scope");
    }

    @Test
    void valueObjectsRejectBlankIdentifiers() {
        assertThatThrownBy(() -> new ConversationScope(" "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("scopeId");

        assertThatThrownBy(() -> new ChatInvocationOrigin("conv-1", " "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("turnId");

        assertThatThrownBy(() -> new TaskInvocationOrigin("run-1", "", "attempt-1"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("taskId");

        assertThatThrownBy(() -> InvocationHandle.create(
                "",
                InvocationType.CHAT,
                new ChatInvocationOrigin("conv-1", "turn-1"),
                "corr-1",
                new ExecutionSubjectRef("user", "u-1"),
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                AgentProfileRef.of("agent", "v1"),
                CLOCK.instant().plusSeconds(30)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("invocationId");
    }

    @Test
    void cancellationSourceOnlyAllowsSafeReasonsAndIsOneWay() {
        CancellationSource source = new CancellationSource();

        assertThat(source.token().isCancelled()).isFalse();
        assertThat(source.cancel(KernelErrorCode.CANCELLED)).isTrue();
        assertThat(source.cancel(KernelErrorCode.DEADLINE_EXCEEDED)).isFalse();
        assertThat(source.token().reasonCode()).contains(KernelErrorCode.CANCELLED);
        assertThatThrownBy(source.token()::throwIfCancelled)
                .isInstanceOf(CancellationSource.CancellationException.class)
                .hasMessageContaining("CANCELLED");

        CancellationSource other = new CancellationSource();
        assertThatThrownBy(() -> other.cancel(KernelErrorCode.INTERNAL_ERROR))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("CANCELLED or DEADLINE_EXCEEDED");
    }

    @Test
    void deadlineChecksUseTheHandleDeadlineOnly() {
        InvocationHandle handle = chatHandle(
                InvocationType.CHAT,
                new ChatInvocationOrigin("conv-1", "turn-1"),
                new ConversationScope("conv-1"));

        assertThat(handle.isExpired(CLOCK)).isFalse();
        assertThat(handle.remaining(CLOCK).getSeconds()).isEqualTo(30);
        assertThat(handle.isExpired(Clock.offset(CLOCK, java.time.Duration.ofSeconds(31)))).isTrue();
    }

    private InvocationHandle chatHandle(
            InvocationType type,
            InvocationOrigin origin,
            InvocationScope scope) {
        return InvocationHandle.create(
                "inv-1",
                type,
                origin,
                "corr-1",
                new ExecutionSubjectRef("user", "u-1"),
                new ContextOwnerRef("conversation", "conv-1"),
                scope,
                AgentProfileRef.of("agent", "v1"),
                CLOCK.instant().plusSeconds(30));
    }
}
