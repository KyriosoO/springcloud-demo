package com.dylan.agent.capability.document.profile;

import com.dylan.agent.adapter.api.document.DocumentCorpusKey;

import java.util.List;
import java.util.Objects;

/** exact parent/Policy/evidence 约束下的 Pre-Plan 确定性 Profile 选择器。 */
public final class DocumentRetrievalProfileResolver {
    private final DocumentProfileAssetRegistry profileRegistry;
    private final DocumentPolicyConstraintRegistry policyRegistry;

    public DocumentRetrievalProfileResolver(
            DocumentProfileAssetRegistry profileRegistry,
            DocumentPolicyConstraintRegistry policyRegistry) {
        this.profileRegistry = Objects.requireNonNull(profileRegistry);
        this.policyRegistry = Objects.requireNonNull(policyRegistry);
    }

    public DocumentProfileSelection select(DocumentProfileSelectionCommand command) {
        Objects.requireNonNull(command);
        if (DocumentPlanningProfileProjector.operation(command.capabilityId()) != command.operation()) {
            throw new IllegalArgumentException("document capability/operation selection mismatch");
        }
        if (!command.agentProfileRef().equals(command.authorizationEvidence().agentProfileRef())
                || !command.policyVersion().equals(command.authorizationEvidence().policyVersion())) {
            throw new IllegalArgumentException("document selection exact authorization evidence mismatch");
        }
        DocumentProfileAssetRef assetRef = profileRegistry.requireRef(command.agentProfileRef());
        if (!assetRef.toString().equals(command.profileContributionEvidenceRef())) {
            throw new IllegalArgumentException("document profile contribution does not bind exact child asset");
        }
        DocumentProfileSet profileSet = profileRegistry.require(assetRef);
        DocumentPolicyConstraint policy = policyRegistry.require(command.policyVersion());
        if (!policy.evidenceRef().equals(command.policyContributionEvidenceRef())) {
            throw new IllegalArgumentException("document policy contribution does not bind exact child constraint");
        }
        var allowedNames = require(policy.allowedProfileNamesByDomain().get(command.domain()), "policy profile names");
        var allowedOperations = require(policy.allowedOperationsByDomain().get(command.domain()), "policy operations");
        if (!allowedOperations.contains(command.operation())) {
            throw new IllegalArgumentException("document operation is not allowed by policy");
        }
        List<DocumentRetrievalProfile> candidates = profileSet.profiles().stream()
                .filter(profile -> profile.domain().equals(command.domain()))
                .filter(profile -> allowedNames.contains(profile.profileName()))
                .filter(profile -> profile.allowedOperations().contains(command.operation()))
                .toList();
        DocumentRetrievalProfile selected;
        if (command.requestedProfile() != null) {
            selected = candidates.stream().filter(profile -> profile.profileName().equals(command.requestedProfile()))
                    .findFirst().orElseThrow(() -> new IllegalArgumentException("requested document profile is not allowed"));
        } else {
            List<DocumentRetrievalProfile> defaults = candidates.stream().filter(DocumentRetrievalProfile::defaultProfile).toList();
            if (defaults.size() != 1) {
                throw new IllegalArgumentException("document policy must expose exactly one selectable default profile");
            }
            selected = defaults.get(0);
        }
        List<DocumentCorpusKey> corpora;
        if (command.materialType() != null) {
            if (!selected.allowedMaterialTypes().contains(command.materialType())) {
                throw new IllegalArgumentException("requested document materialType is not allowed by selected profile");
            }
            corpora = List.of(new DocumentCorpusKey(command.domain(), command.materialType()));
        } else {
            corpora = selected.allowedMaterialTypes().stream().sorted()
                    .map(materialType -> new DocumentCorpusKey(command.domain(), materialType)).toList();
        }
        String selectionDigest = DocumentProfileCanonicalizer.selectionDigest(
                assetRef, selected.profileName(), policy.evidenceRef(), command.capabilityId(),
                command.domain(), command.materialType());
        return new DocumentProfileSelection(assetRef, selected.profileName(), selected, policy, corpora, selectionDigest);
    }

    private static <T> T require(T value, String name) {
        if (value == null) throw new IllegalArgumentException(name + " are missing for selected domain");
        return value;
    }
}
