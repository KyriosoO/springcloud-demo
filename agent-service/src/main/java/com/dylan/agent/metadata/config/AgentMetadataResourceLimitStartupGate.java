package com.dylan.agent.metadata.config;

import com.dylan.agent.adapter.api.operation.CapabilityResourceLimit;
import com.dylan.agent.kernel.definition.CapabilityDefinition;
import com.dylan.agent.kernel.registration.CapabilityRegistry;
import com.dylan.agent.metadata.authorization.resource.ResourceLimitSource;

import java.util.Collection;
import java.util.Objects;

/** 启动时闭合 Capability Definition 与所有 Profile/Policy typed contribution。 */
public final class AgentMetadataResourceLimitStartupGate {

    public AgentMetadataResourceLimitStartupGate(
            AgentMetadataStore metadataStore,
            CapabilityRegistry capabilityRegistry) {
        validate(
                Objects.requireNonNull(metadataStore, "metadataStore must not be null").current(),
                Objects.requireNonNull(capabilityRegistry, "capabilityRegistry must not be null")
                        .registrations().stream()
                        .map(registration -> registration.definition())
                        .toList());
    }

    static void validate(
            AgentMetadataBundle bundle,
            Collection<CapabilityDefinition> definitions) {
        Objects.requireNonNull(bundle, "bundle must not be null");
        Objects.requireNonNull(definitions, "definitions must not be null");
        for (CapabilityDefinition definition : definitions) {
            requireContributions(bundle, definition);
        }
    }

    private static <T extends CapabilityResourceLimit> void requireContributions(
            AgentMetadataBundle bundle,
            CapabilityDefinition definition) {
        requireTypedContributions(bundle, definition, definition.resourceLimitDeclaration());
    }

    private static <T extends CapabilityResourceLimit> void requireTypedContributions(
            AgentMetadataBundle bundle,
            CapabilityDefinition definition,
            com.dylan.agent.kernel.resource.CapabilityResourceLimitDeclaration<T> declaration) {
        bundle.profileVersionIndex().values().forEach(profile ->
                profile.resourceLimitContributions().require(
                        ResourceLimitSource.PROFILE,
                        declaration.contractRef(),
                        declaration.limitType()));
        bundle.policyVersionIndex().values().forEach(policy ->
                policy.resourceLimitContributions().require(
                        ResourceLimitSource.POLICY,
                        declaration.contractRef(),
                        declaration.limitType()));
    }
}
