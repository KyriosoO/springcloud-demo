package com.dylan.agent.metadata;

import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.kernel.port.model.ExpectedContextVersion;
import com.dylan.agent.metadata.context.internal.ContextRecordEntity;
import com.dylan.agent.metadata.context.internal.ContextRepository;

import java.time.Instant;

final class NoopContextRepository implements ContextRepository {
    @Override
    public void upsertApproved(ContextRecordEntity record, ExpectedContextVersion expectedVersion) {
    }

    @Override
    public void markConversationUnreadable(ConversationScope scope, Instant now) {
    }

    @Override
    public int deleteExpired(Instant cutoff, int limit) {
        return 0;
    }
}
