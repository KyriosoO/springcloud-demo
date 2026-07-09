package com.dylan.agent.capability.document.security;

import com.dylan.agent.config.AgentProperties;

import java.util.List;
import java.util.Objects;

/** 文档本地撤权和应急禁用守卫。 */
public final class DocumentRevocationGuard {

    private final AgentProperties properties;

    public DocumentRevocationGuard(AgentProperties properties) {
        this.properties = Objects.requireNonNull(properties, "properties must not be null");
    }

    public DocumentRevocationDecision evaluate(String domain, String indexVersion) {
        return evaluate(domain, indexVersion, null, null, null);
    }

    public DocumentRevocationDecision evaluate(
            String domain,
            String indexVersion,
            String retrievalProfile,
            String profileVersion,
            String indexAlias) {
        var blocklist = properties.getDocument().getBlocklist();
        if (contains(blocklist.getDomains(), domain)) {
            return DocumentRevocationDecision.localBlocklist("DOMAIN", domain);
        }
        if (contains(blocklist.getIndexVersions(), indexVersion)) {
            return DocumentRevocationDecision.localBlocklist("INDEX_VERSION", indexVersion);
        }
        if (contains(blocklist.getRetrievalProfiles(), retrievalProfile)) {
            return DocumentRevocationDecision.localBlocklist("RETRIEVAL_PROFILE", retrievalProfile);
        }
        if (contains(blocklist.getProfileVersions(), profileVersion)) {
            return DocumentRevocationDecision.localBlocklist("PROFILE_VERSION", profileVersion);
        }
        if (contains(blocklist.getIndexAliases(), indexAlias)) {
            return DocumentRevocationDecision.localBlocklist("INDEX_ALIAS", indexAlias);
        }
        return DocumentRevocationDecision.allowed();
    }

    public void assertAllowed(String domain, String indexVersion) {
        DocumentRevocationDecision decision = evaluate(domain, indexVersion);
        if (decision.revoked()) {
            throw new IllegalStateException("document access revoked by " + decision.source() + ":" + decision.target());
        }
    }

    public void assertAllowed(
            String domain,
            String indexVersion,
            String retrievalProfile,
            String profileVersion,
            String indexAlias) {
        DocumentRevocationDecision decision = evaluate(
                domain,
                indexVersion,
                retrievalProfile,
                profileVersion,
                indexAlias);
        if (decision.revoked()) {
            throw new IllegalStateException("document access revoked by " + decision.source() + ":" + decision.target());
        }
    }

    private static boolean contains(List<String> values, String candidate) {
        if (candidate == null || candidate.isBlank() || values == null) {
            return false;
        }
        return values.stream()
                .filter(Objects::nonNull)
                .map(String::trim)
                .anyMatch(candidate::equals);
    }
}
