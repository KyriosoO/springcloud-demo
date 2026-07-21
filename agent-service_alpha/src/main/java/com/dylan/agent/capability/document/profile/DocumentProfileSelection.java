package com.dylan.agent.capability.document.profile;

import com.dylan.agent.adapter.api.document.DocumentCorpusKey;

import java.util.List;
import java.util.Objects;

/** server-internal immutable 选择结果；构造器仅对本 Profile 包开放。 */
public final class DocumentProfileSelection {
    private final DocumentProfileAssetRef assetRef;
    private final String selectedProfileName;
    private final DocumentRetrievalProfile selectedProfile;
    private final DocumentPolicyConstraint policyConstraint;
    private final List<DocumentCorpusKey> allowedCorpora;
    private final String selectionDigest;

    DocumentProfileSelection(
            DocumentProfileAssetRef assetRef,
            String selectedProfileName,
            DocumentRetrievalProfile selectedProfile,
            DocumentPolicyConstraint policyConstraint,
            List<DocumentCorpusKey> allowedCorpora,
            String selectionDigest) {
        this.assetRef = Objects.requireNonNull(assetRef);
        this.selectedProfile = Objects.requireNonNull(selectedProfile);
        if (selectedProfileName == null || !selectedProfileName.equals(selectedProfile.profileName())) {
            throw new IllegalArgumentException("selected document profile name mismatch");
        }
        this.selectedProfileName = selectedProfileName;
        this.policyConstraint = Objects.requireNonNull(policyConstraint);
        this.allowedCorpora = List.copyOf(Objects.requireNonNull(allowedCorpora));
        if (this.allowedCorpora.isEmpty()) throw new IllegalArgumentException("document selection has no allowed corpus");
        if (selectionDigest == null || !selectionDigest.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("invalid document profile selection digest");
        }
        this.selectionDigest = selectionDigest;
    }

    public DocumentProfileAssetRef assetRef() { return assetRef; }
    public String selectedProfileName() { return selectedProfileName; }
    public DocumentRetrievalProfile selectedProfile() { return selectedProfile; }
    public DocumentPolicyConstraint policyConstraint() { return policyConstraint; }
    public List<DocumentCorpusKey> allowedCorpora() { return allowedCorpora; }
    public String selectionDigest() { return selectionDigest; }
}
