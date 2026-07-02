package com.dylan.agent.metadata.config;

import com.dylan.agent.metadata.policy.model.AgentPolicySnapshot;
import com.dylan.agent.metadata.profile.model.AgentProfileDefinition;
import com.dylan.agent.metadata.profile.model.AgentProfileVersionKey;
import com.dylan.agent.metadata.profile.model.ProfileBehaviorAsset;
import com.dylan.agent.metadata.profile.model.ProfileBehaviorAssetRef;

import java.util.Map;
import java.util.Objects;

/** 面向 Profile/Policy/Context/Security 的一次原子发布 metadata bundle。 */
public record AgentMetadataBundle(
        String bundleVersion,
        String bundleDigest,
        String defaultProfileId,
        Map<String, String> activeProfileVersions,
        String activePolicyVersion,
        AgentSecuritySettings securitySettings,
        Map<AgentProfileVersionKey, AgentProfileDefinition> profileVersionIndex,
        Map<ProfileBehaviorAssetRef, ProfileBehaviorAsset> behaviorAssetVersionIndex,
        Map<String, AgentPolicySnapshot> policyVersionIndex) {

    public AgentMetadataBundle {
        bundleVersion = requireNonBlank(bundleVersion, "bundleVersion");
        bundleDigest = requireNonBlank(bundleDigest, "bundleDigest");
        defaultProfileId = requireNonBlank(defaultProfileId, "defaultProfileId");
        activeProfileVersions = Map.copyOf(Objects.requireNonNull(activeProfileVersions, "activeProfileVersions must not be null"));
        activePolicyVersion = requireNonBlank(activePolicyVersion, "activePolicyVersion");
        Objects.requireNonNull(securitySettings, "securitySettings must not be null");
        profileVersionIndex = Map.copyOf(Objects.requireNonNull(profileVersionIndex, "profileVersionIndex must not be null"));
        behaviorAssetVersionIndex = Map.copyOf(Objects.requireNonNull(behaviorAssetVersionIndex, "behaviorAssetVersionIndex must not be null"));
        policyVersionIndex = Map.copyOf(Objects.requireNonNull(policyVersionIndex, "policyVersionIndex must not be null"));
        if (!policyVersionIndex.containsKey(activePolicyVersion)) {
            throw new IllegalArgumentException("activePolicyVersion must exist in policyVersionIndex");
        }
    }

    public AgentProfileDefinition requireProfile(AgentProfileVersionKey key) {
        AgentProfileDefinition profile = profileVersionIndex.get(Objects.requireNonNull(key));
        if (profile == null) {
            throw new IllegalStateException("unknown profile version: " + key);
        }
        return profile;
    }

    public AgentPolicySnapshot activePolicy() {
        return policyVersionIndex.get(activePolicyVersion);
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
