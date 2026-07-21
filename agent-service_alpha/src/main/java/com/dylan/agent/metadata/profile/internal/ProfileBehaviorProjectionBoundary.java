package com.dylan.agent.metadata.profile.internal;

import com.dylan.agent.api.contract.runtime.common.RuntimeProfileBehaviorProjection;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.config.AgentMetadataStore;

import java.util.Objects;

/** 只投影已评审 behavior instructions；capability/policy/permission facts 不泄露给 Runtime。 */
public final class ProfileBehaviorProjectionBoundary {

    private final AgentMetadataStore store;

    public ProfileBehaviorProjectionBoundary(AgentMetadataStore store) {
        this.store = Objects.requireNonNull(store);
    }

    public RuntimeProfileBehaviorProjection project(PlanningAuthorizationEvidence evidence) {
        Objects.requireNonNull(evidence, "evidence must not be null");
        var bundle = store.current();
        if (!bundle.bundleVersion().equals(evidence.metadataBundleVersion())
                || !bundle.bundleDigest().equals(evidence.metadataBundleDigest())) {
            throw new IllegalStateException("metadata evidence is stale");
        }
        var profile = bundle.requireProfile(evidence.profileKey());
        var asset = bundle.behaviorAssetVersionIndex().get(profile.promptProfileRef());
        if (asset == null) {
            throw new IllegalStateException("profile behavior asset missing: " + profile.promptProfileRef());
        }
        RuntimeProfileBehaviorProjection projection = new RuntimeProfileBehaviorProjection();
        projection.setInstructions(asset.instructions());
        projection.setLocale(asset.locale().map(java.util.Locale::toLanguageTag).orElse(null));
        return projection;
    }
}
