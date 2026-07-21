package com.dylan.agent.capability.document.profile;

import com.dylan.agent.shared.ref.AgentProfileRef;

import java.util.Map;
import java.util.Objects;

/** exact immutable child asset lookup；刻意不提供 latest/active API。 */
public final class DocumentProfileAssetRegistry {
    private final Map<DocumentProfileAssetRef, DocumentProfileSet> assets;
    private final Map<AgentProfileRef, DocumentProfileAssetRef> refsByOwner;

    DocumentProfileAssetRegistry(Map<DocumentProfileAssetRef, DocumentProfileSet> assets) {
        this.assets = Map.copyOf(Objects.requireNonNull(assets));
        var owners = new java.util.LinkedHashMap<AgentProfileRef, DocumentProfileAssetRef>();
        this.assets.forEach((ref, value) -> {
            if (!ref.agentProfileRef().equals(value.ownerProfileRef())
                    || !ref.documentProfileVersion().equals(value.documentProfileVersion())) {
                throw new IllegalArgumentException("document profile asset ref/value mismatch");
            }
            if (owners.putIfAbsent(ref.agentProfileRef(), ref) != null) {
                throw new IllegalArgumentException("duplicate document profile asset owner");
            }
        });
        refsByOwner = Map.copyOf(owners);
    }

    public DocumentProfileSet require(DocumentProfileAssetRef ref) {
        DocumentProfileSet result = assets.get(Objects.requireNonNull(ref));
        if (result == null) throw new IllegalArgumentException("document profile asset is unavailable");
        return result;
    }

    public DocumentProfileAssetRef requireRef(AgentProfileRef owner) {
        DocumentProfileAssetRef ref = refsByOwner.get(Objects.requireNonNull(owner));
        if (ref == null) throw new IllegalArgumentException("document profile asset owner is unavailable");
        return ref;
    }
}
