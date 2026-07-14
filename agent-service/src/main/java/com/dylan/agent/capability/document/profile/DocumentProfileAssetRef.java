package com.dylan.agent.capability.document.profile;

import com.dylan.agent.shared.ref.AgentProfileRef;

import java.util.Objects;

/** Profile contribution 使用的 exact child asset 安全引用。 */
public record DocumentProfileAssetRef(
        AgentProfileRef agentProfileRef,
        String documentProfileVersion,
        String assetDigest) {
    public DocumentProfileAssetRef {
        Objects.requireNonNull(agentProfileRef);
        if (agentProfileRef.expectedVersion().isEmpty()) throw new IllegalArgumentException("agentProfileRef must be exact");
        if (documentProfileVersion == null || !documentProfileVersion.matches("dp1-[0-9a-f]{64}")) {
            throw new IllegalArgumentException("invalid documentProfileVersion");
        }
        if (assetDigest == null || !assetDigest.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("invalid document profile asset digest");
        }
    }

    @Override
    public String toString() {
        return agentProfileRef.agentId() + "@" + agentProfileRef.expectedVersion().orElseThrow()
                + ":" + documentProfileVersion + ":" + assetDigest;
    }
}
