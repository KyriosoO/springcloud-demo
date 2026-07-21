package com.dylan.agent.capability.document.rewrite;

import java.util.List;

/** 单次请求冻结后的查询变体，不再被 Runtime 输出覆盖。 */
public record QueryVariants(
        String normalizedQuery,
        List<String> ruleKeywords,
        List<String> rewriteCandidates,
        int rejectedCount,
        String rewriteCandidateDigest) {
}
