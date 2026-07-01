package com.dylan.agent.metadata.context.internal;

import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.lifecycle.port.ContextScopeRetirementParticipant;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.Objects;

/** Marks ConversationScope contexts unreadable before physical cleanup. */
public final class ContextScopeRetirementParticipantImpl implements ContextScopeRetirementParticipant {

    private final ContextRepository repository;

    public ContextScopeRetirementParticipantImpl(ContextRepository repository) {
        this.repository = Objects.requireNonNull(repository);
    }

    @Override
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void retire(ConversationScope scope, Instant now) {
        repository.markConversationUnreadable(
                Objects.requireNonNull(scope),
                Objects.requireNonNull(now));
    }
}
