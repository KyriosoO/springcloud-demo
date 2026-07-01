package com.dylan.agent.metadata.context.internal;

import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.kernel.port.model.ExpectedContextVersion;

import java.time.Instant;

/** Repository seam for D02_03 context persistence. */
public interface ContextRepository {

    void upsertApproved(ContextRecordEntity record, ExpectedContextVersion expectedVersion);

    void markConversationUnreadable(ConversationScope scope, Instant now);

    int deleteExpired(Instant cutoff, int limit);
}
