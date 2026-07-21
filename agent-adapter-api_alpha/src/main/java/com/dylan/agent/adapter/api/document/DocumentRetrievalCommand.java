package com.dylan.agent.adapter.api.document;

import java.util.List;

/** 文档 Adapter 唯一检索命令；不含 alias、physical index、JWT、Provider 配置或 raw ACL。 */
public record DocumentRetrievalCommand(
        DocumentCorpusKey corpusKey,
        DocumentRetrievalExecutionBinding executionBinding,
        List<ValidatedDocumentCallerFilter> callerFilters,
        DocumentProtectedFilterBinding protectedFilter,
        DocumentPreparedQuery preparedQuery,
        DocumentRetrievalChannels channels,
        DocumentFusionSpec fusion,
        DocumentDedupSpec dedup,
        DocumentContextSpec context) {
    public DocumentRetrievalCommand {
        if (corpusKey == null || executionBinding == null || protectedFilter == null
                || preparedQuery == null || channels == null || fusion == null || dedup == null || context == null) {
            throw new IllegalArgumentException("document retrieval command incomplete");
        }
        callerFilters = List.copyOf(callerFilters == null ? List.of() : callerFilters);
        if (!corpusKey.equals(protectedFilter.corpusKey())
                || !executionBinding.aclEvidenceDigest().equals(protectedFilter.aclEvidenceDigest())
                || !executionBinding.profileProjectionDigest().equals(protectedFilter.profileProjectionDigest())
                || !executionBinding.resourceLimitReference().equals(protectedFilter.resourceLimitReference())) {
            throw new IllegalArgumentException("document retrieval command security binding mismatch");
        }
    }
}
