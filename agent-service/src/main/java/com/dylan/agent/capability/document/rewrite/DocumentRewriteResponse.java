package com.dylan.agent.capability.document.rewrite;

import java.util.List;

/** Runtime 改写响应；所有候选均需 Java 再校验。 */
public record DocumentRewriteResponse(
        List<DocumentRewriteCandidate> candidates,
        String diagnosticId,
        String model) {
}
