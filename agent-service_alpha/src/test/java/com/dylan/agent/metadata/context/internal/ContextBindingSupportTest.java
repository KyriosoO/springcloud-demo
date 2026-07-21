package com.dylan.agent.metadata.context.internal;

import static org.assertj.core.api.Assertions.assertThat;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.metadata.context.model.ContextRecordKey;
import com.dylan.agent.metadata.crypto.model.ProtectedPayload;

import java.time.Instant;

import org.junit.jupiter.api.Test;

class ContextBindingSupportTest {

    @Test
    void bindingDigestIsUnambiguousWhenValuesContainSeparators() {
        ContextRecordEntity first = entity("owner", "scope|with-pipe");
        ContextRecordEntity second = entity("owner|scope", "with-pipe");

        assertThat(ContextBindingSupport.bindingDigest(first))
                .isNotEqualTo(ContextBindingSupport.bindingDigest(second));
    }

    private static ContextRecordEntity entity(String ownerId, String scopeId) {
        return new ContextRecordEntity(
                "ctx-1",
                new ContextRecordKey(
                        new ContextOwnerRef("conversation", ownerId),
                        new ConversationScope(scopeId),
                        RuntimeContextType.QUERY),
                AgentExecutionContracts.QUERY_CONTEXT,
                1,
                new ProtectedPayload(new byte[] {1}, "key", new byte[] {2}, "v1"),
                "query.search",
                "inv-1",
                "employee",
                true,
                Instant.parse("2026-07-03T00:00:00Z"));
    }
}
