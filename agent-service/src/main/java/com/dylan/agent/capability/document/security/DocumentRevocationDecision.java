package com.dylan.agent.capability.document.security;

/** 文档本地撤权或应急禁用决策。 */
public record DocumentRevocationDecision(
        boolean revoked,
        String source,
        String target,
        String targetId,
        String reason) {

    public static DocumentRevocationDecision allowed() {
        return new DocumentRevocationDecision(false, "NONE", "", "", "");
    }

    public static DocumentRevocationDecision localBlocklist(String target, String targetId) {
        return new DocumentRevocationDecision(true, "LOCAL_BLOCKLIST", target, targetId, "document target is blocklisted");
    }
}
