package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.DocumentHybridOptions;

/** Java 侧冻结后的文档检索 profile。 */
public record DocumentRetrievalProfile(
        String domain,
        String materialType,
        String retrievalProfile,
        String profileVersion,
        String indexAlias,
        DocumentHybridOptions hybridOptions) {
}
