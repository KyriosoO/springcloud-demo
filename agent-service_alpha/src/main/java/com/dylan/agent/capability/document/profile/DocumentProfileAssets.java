package com.dylan.agent.capability.document.profile;

import com.dylan.agent.adapter.api.document.DocumentRetrievalChannel;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.shared.ref.AgentProfileRef;

import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/** 配置输入到 immutable Profile/Policy child assets 的唯一构建器。 */
public final class DocumentProfileAssets {
    private DocumentProfileAssets() {}

    public static BuiltAssets build(DocumentProfileProperties properties) {
        AgentProfileRef owner = AgentProfileRef.of(text(properties.getOwnerAgentId(), "ownerAgentId"),
                text(properties.getOwnerProfileVersion(), "ownerProfileVersion"));
        List<DocumentRetrievalProfile> profiles = properties.getDefinitions().stream()
                .map(DocumentProfileAssets::profile)
                .toList();
        var canonical = DocumentProfileCanonicalizer.canonicalize(owner, profiles);
        DocumentProfileSet profileSet = new DocumentProfileSet(owner, canonical.documentProfileVersion(), profiles);
        DocumentProfileAssetRef assetRef = new DocumentProfileAssetRef(
                owner, canonical.documentProfileVersion(), canonical.assetDigest());
        DocumentProfileAssetRegistry profileRegistry = new DocumentProfileAssetRegistry(Map.of(assetRef, profileSet));

        String policyVersion = text(properties.getPolicyVersion(), "policyVersion");
        var allowedProfiles = new LinkedHashMap<String, Set<String>>();
        var allowedChannels = new LinkedHashMap<String, Set<DocumentRetrievalChannel>>();
        var allowedOperations = new LinkedHashMap<String, Set<DocumentPlanOperation>>();
        for (DocumentProfileProperties.PolicyEntry entry : properties.getPolicy()) {
            String domain = text(entry.getDomain(), "policy domain");
            if (allowedProfiles.putIfAbsent(domain, strings(entry.getAllowedProfileNames())) != null
                    || allowedChannels.putIfAbsent(domain, channels(entry.getAllowedChannels())) != null
                    || allowedOperations.putIfAbsent(domain, operations(entry.getAllowedOperations())) != null) {
                throw new IllegalArgumentException("duplicate document policy domain");
            }
        }
        String policyDigest = DocumentProfileCanonicalizer.policyDigest(
                policyVersion, allowedProfiles, allowedChannels, allowedOperations);
        DocumentPolicyConstraint constraint = new DocumentPolicyConstraint(
                policyVersion, allowedProfiles, allowedChannels, allowedOperations, policyDigest);
        validateClosure(profileSet, constraint);
        return new BuiltAssets(profileRegistry,
                new DocumentPolicyConstraintRegistry(Map.of(policyVersion, constraint)), assetRef, constraint);
    }

    private static DocumentRetrievalProfile profile(DocumentProfileProperties.Entry entry) {
        String domain = text(entry.getDomain(), "profile domain");
        Set<DocumentRetrievalChannel> channels = channels(entry.getAllowedChannels());
        Set<DocumentRetrievalChannel> required = entry.getRequiredChannels().isEmpty()
                ? Set.of()
                : channels(entry.getRequiredChannels());
        var weights = new EnumMap<DocumentRetrievalChannel, Integer>(DocumentRetrievalChannel.class);
        channels.forEach(channel -> weights.put(channel, entry.getChannelWeights().getOrDefault(channel.name(), 1)));
        Set<DocumentPlanOperation> operations = operations(entry.getAllowedOperations());
        var generations = new EnumMap<DocumentPlanOperation, DocumentFeaturePolicy>(DocumentPlanOperation.class);
        entry.getGenerationPolicy().forEach((operation, policy) ->
                generations.put(DocumentPlanOperation.valueOf(operation.trim().toUpperCase(Locale.ROOT)), policy));
        return new DocumentRetrievalProfile(
                domain,
                text(entry.getProfileName(), "profileName"),
                entry.isDefaultProfile(),
                strings(entry.getAllowedMaterialTypes()),
                operations,
                channels,
                required,
                weights,
                new DocumentFusionPolicy(entry.getKeywordK(), entry.getVectorK(), entry.getRrfK(),
                        entry.getNumCandidates(), entry.getRerankTopN()),
                new DocumentDedupPolicy(entry.getMaxChunksPerDocument()),
                new DocumentContextPolicy(entry.getContextBeforeChunks(), entry.getContextAfterChunks()),
                entry.getRewritePolicy(),
                entry.getEmbeddingPolicy(),
                entry.getRerankPolicy(),
                generations,
                fields(domain, entry.getSearchableFields()),
                fields(domain, entry.getReturnableFields()));
    }

    private static void validateClosure(DocumentProfileSet profileSet, DocumentPolicyConstraint policy) {
        Set<String> domains = profileSet.profiles().stream().map(DocumentRetrievalProfile::domain)
                .collect(java.util.stream.Collectors.toUnmodifiableSet());
        if (!policy.allowedProfileNamesByDomain().keySet().equals(domains)) {
            throw new IllegalArgumentException("document policy must explicitly cover every profile domain");
        }
        for (String domain : domains) {
            List<DocumentRetrievalProfile> profiles = profileSet.profiles().stream()
                    .filter(profile -> profile.domain().equals(domain)).toList();
            Set<String> names = profiles.stream().map(DocumentRetrievalProfile::profileName)
                    .collect(java.util.stream.Collectors.toUnmodifiableSet());
            if (!names.containsAll(policy.allowedProfileNamesByDomain().get(domain))) {
                throw new IllegalArgumentException("document policy references unknown profile");
            }
            long allowedDefaults = profiles.stream().filter(DocumentRetrievalProfile::defaultProfile)
                    .filter(profile -> policy.allowedProfileNamesByDomain().get(domain).contains(profile.profileName()))
                    .count();
            if (allowedDefaults != 1) {
                throw new IllegalArgumentException("document policy must allow exactly one default profile per domain");
            }
            for (DocumentRetrievalProfile profile : profiles) {
                if (policy.allowedProfileNamesByDomain().get(domain).contains(profile.profileName())
                        && (!policy.allowedChannelsByDomain().get(domain).containsAll(profile.requiredChannels())
                        || java.util.Collections.disjoint(profile.allowedChannels(), policy.allowedChannelsByDomain().get(domain))
                        || java.util.Collections.disjoint(profile.allowedOperations(), policy.allowedOperationsByDomain().get(domain)))) {
                    throw new IllegalArgumentException("document policy removes a required channel or every allowed operation");
                }
            }
        }
    }

    private static Set<CanonicalFieldRef> fields(String domain, List<String> values) {
        if (values.size() > 256) throw new IllegalArgumentException("too many document field refs");
        return values.stream().map(value -> new CanonicalFieldRef(domain, text(value, "field")))
                .collect(java.util.stream.Collectors.toUnmodifiableSet());
    }

    private static Set<String> strings(List<String> values) {
        if (values == null || values.isEmpty() || values.size() > 32) {
            throw new IllegalArgumentException("document configured set must contain 1..32 values");
        }
        Set<String> result = values.stream().map(value -> text(value, "configured value"))
                .collect(java.util.stream.Collectors.toCollection(LinkedHashSet::new));
        if (result.size() != values.size()) throw new IllegalArgumentException("duplicate document configured value");
        return Set.copyOf(result);
    }

    private static Set<DocumentRetrievalChannel> channels(List<String> values) {
        return strings(values).stream().map(value -> DocumentRetrievalChannel.valueOf(value.toUpperCase(Locale.ROOT)))
                .collect(java.util.stream.Collectors.toUnmodifiableSet());
    }

    private static Set<DocumentPlanOperation> operations(List<String> values) {
        return strings(values).stream().map(value -> DocumentPlanOperation.valueOf(value.toUpperCase(Locale.ROOT)))
                .collect(java.util.stream.Collectors.toUnmodifiableSet());
    }

    private static String text(String value, String name) {
        if (value == null || value.trim().isEmpty()) throw new IllegalArgumentException(name + " must not be blank");
        return value.trim();
    }

    public record BuiltAssets(
            DocumentProfileAssetRegistry profileRegistry,
            DocumentPolicyConstraintRegistry policyRegistry,
            DocumentProfileAssetRef assetRef,
            DocumentPolicyConstraint policyConstraint) {}
}
