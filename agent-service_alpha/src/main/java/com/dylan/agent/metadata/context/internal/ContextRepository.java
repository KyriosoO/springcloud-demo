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

    /**
     * 按逻辑 key 读取权威记录，不按 readable 或 expires_at 过滤，用于 CAS/currentness 判断。
     */
    default Optional<ContextRecordEntity> findByKey(
            com.dylan.agent.metadata.context.model.ContextRecordKey key) {
        return Optional.empty();
    }

    void upsertApproved(ContextRecordEntity record, ExpectedContextVersion expectedVersion);

    void markConversationUnreadable(ConversationScope scope, Instant now);

    int deleteExpired(Instant cutoff, int limit);
}
