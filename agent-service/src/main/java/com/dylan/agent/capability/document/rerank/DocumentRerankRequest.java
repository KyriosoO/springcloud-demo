package com.dylan.agent.capability.document.rerank;

import com.dylan.agent.adapter.api.document.AdapterDocumentResult;

import java.time.Instant;

/** rerank 请求，不包含 ACL 明细或完整 provider prompt。 */
public record DocumentRerankRequest(
        String invocationId,
        String domain,
        String materialType,
        String retrievalProfile,
        String queryText,
        int topN,
        AdapterDocumentResult candidates,
        Instant absoluteDeadline) {
}
