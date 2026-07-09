package com.dylan.agent.capability.document.security;

import com.dylan.agent.testsupport.DomainMetadataTestSupport;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentRevocationGuardTest {

    @Test
    void allowsDocumentWhenNoLocalBlocklistMatches() {
        var guard = new DocumentRevocationGuard(DomainMetadataTestSupport.agentProperties());

        DocumentRevocationDecision decision = guard.evaluate(
                "policy_document",
                "idx-v1",
                "tax-v2",
                "profile-v1",
                "agent-doc-tax-policy-read");

        assertThat(decision.revoked()).isFalse();
    }

    @Test
    void revokesDomainFromLocalBlocklist() {
        var properties = DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getBlocklist().setDomains(List.of("policy_document"));
        var guard = new DocumentRevocationGuard(properties);

        DocumentRevocationDecision decision = guard.evaluate("policy_document", "idx-v1");

        assertThat(decision.revoked()).isTrue();
        assertThat(decision.source()).isEqualTo("LOCAL_BLOCKLIST");
        assertThat(decision.target()).isEqualTo("DOMAIN");
    }

    @Test
    void failsClosedForBlocklistedIndexVersion() {
        var properties = DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getBlocklist().setIndexVersions(List.of("idx-v1"));
        var guard = new DocumentRevocationGuard(properties);

        assertThatThrownBy(() -> guard.assertAllowed("policy_document", "idx-v1"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("document access revoked");
    }

    @Test
    void revokesProfileAndIndexAliasFromLocalBlocklist() {
        var properties = DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getBlocklist().setRetrievalProfiles(List.of("tax-v2"));
        properties.getDocument().getBlocklist().setProfileVersions(List.of("profile-v1"));
        properties.getDocument().getBlocklist().setIndexAliases(List.of("agent-doc-tax-policy-read"));
        var guard = new DocumentRevocationGuard(properties);

        DocumentRevocationDecision profileDecision = guard.evaluate(
                "policy_document",
                "idx-v1",
                "tax-v2",
                null,
                null);
        DocumentRevocationDecision profileVersionDecision = guard.evaluate(
                "policy_document",
                "idx-v1",
                "other-profile",
                "profile-v1",
                null);
        DocumentRevocationDecision indexAliasDecision = guard.evaluate(
                "policy_document",
                "idx-v1",
                "other-profile",
                "other-version",
                "agent-doc-tax-policy-read");

        assertThat(profileDecision.revoked()).isTrue();
        assertThat(profileDecision.target()).isEqualTo("RETRIEVAL_PROFILE");
        assertThat(profileVersionDecision.revoked()).isTrue();
        assertThat(profileVersionDecision.target()).isEqualTo("PROFILE_VERSION");
        assertThat(indexAliasDecision.revoked()).isTrue();
        assertThat(indexAliasDecision.target()).isEqualTo("INDEX_ALIAS");
    }
}
