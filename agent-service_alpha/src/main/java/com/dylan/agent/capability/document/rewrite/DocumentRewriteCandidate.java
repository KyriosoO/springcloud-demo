package com.dylan.agent.capability.document.rewrite;

/** Runtime 返回的单条不可信改写候选。 */
public record DocumentRewriteCandidate(
        String text,
        String intentLabel,
        Double confidence) {
}
