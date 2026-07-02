package com.dylan.agent.metadata.profile.internal;

import com.dylan.agent.kernel.registration.CapabilityRegistry;
import com.dylan.agent.metadata.config.AgentMetadataStore;
import com.dylan.agent.metadata.profile.model.AgentProfileDefinition;
import com.dylan.agent.metadata.profile.model.AgentProfileVersionKey;
import com.dylan.agent.shared.ref.AgentProfileRef;

import java.util.Collection;
import java.util.Objects;

/** Read-only profile definition boundary backed by one atomic metadata bundle. */
public final class AgentProfileRegistry {

    private final AgentMetadataStore store;

    public AgentProfileRegistry(AgentMetadataStore store) {
        this.store = Objects.requireNonNull(store);
    }

    public AgentProfileDefinition getRequired(AgentProfileRef ref) {
        Objects.requireNonNull(ref, "ref must not be null");
        String version = ref.expectedVersion().orElseGet(() -> activeVersion(ref.agentId()));
        return store.current().requireProfile(new AgentProfileVersionKey(ref.agentId(), version));
    }

    public AgentProfileRef defaultRef() {
        var bundle = store.current();
        String version = activeVersion(bundle.defaultProfileId());
        return AgentProfileRef.of(bundle.defaultProfileId(), version);
    }

    public Collection<AgentProfileDefinition> activeProfiles() {
        var bundle = store.current();
        return bundle.activeProfileVersions().entrySet().stream()
                .map(entry -> bundle.requireProfile(new AgentProfileVersionKey(entry.getKey(), entry.getValue())))
                .toList();
    }

    public String activeVersion(String agentId) {
        String version = store.current().activeProfileVersions().get(agentId);
        if (version == null) {
            throw new IllegalStateException("profile has no active version: " + agentId);
        }
        return version;
    }

    public void validateReferences(CapabilityRegistry capabilityRegistry) {
        Objects.requireNonNull(capabilityRegistry, "capabilityRegistry must not be null");
        for (AgentProfileDefinition profile : activeProfiles()) {
            for (String capabilityId : profile.allowedCapabilityIds()) {
                capabilityRegistry.resolve(capabilityId);
            }
        }
    }
}
