package com.dylan.agent.capability.document.rewrite;

import java.time.Instant;

/** Runtime LLM 改写请求；不包含 ACL、indexAlias、profile 或 ES DSL。 */
public record DocumentRewriteRequest(
        String requestId,
        String query,
        String domain,
        String materialType,
        String language,
        int maxCandidates,
        long timeoutMs,
        Instant deadline) {
}
