package com.dylan.agent.metadata.context.internal;

import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.kernel.port.model.ExpectedContextVersion;

import java.time.Instant;
import java.util.Optional;

/** D02_03 context persistence 的 repository seam。 */
public interface ContextRepository {

    default Optional<ContextRecordEntity> findCurrent(
            com.dylan.agent.metadata.context.model.ContextRecordKey key,
            Instant now) {
        return Optional.empty();
    }

    void upsertApproved(ContextRecordEntity record, ExpectedContextVersion expectedVersion);

    void markConversationUnreadable(ConversationScope scope, Instant now);

    int deleteExpired(Instant cutoff, int limit);
}
