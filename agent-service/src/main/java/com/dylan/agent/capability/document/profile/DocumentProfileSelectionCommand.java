package com.dylan.agent.capability.document.profile;

import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.shared.ref.AgentProfileRef;

import java.util.Objects;

/** Route 后、Plan 前唯一允许进入 Document Profile 选择器的受控输入。 */
public record DocumentProfileSelectionCommand(
        String capabilityId,
        String domain,
        DocumentPlanOperation operation,
        AgentProfileRef agentProfileRef,
        String policyVersion,
        PlanningAuthorizationEvidence authorizationEvidence,
        String profileContributionEvidenceRef,
        String policyContributionEvidenceRef,
        String requestedProfile,
        String materialType) {
    public DocumentProfileSelectionCommand {
        capabilityId = text(capabilityId, "capabilityId");
        domain = text(domain, "domain");
        Objects.requireNonNull(operation);
        Objects.requireNonNull(agentProfileRef);
        if (agentProfileRef.expectedVersion().isEmpty()) throw new IllegalArgumentException("agentProfileRef must be exact");
        policyVersion = text(policyVersion, "policyVersion");
        Objects.requireNonNull(authorizationEvidence);
        profileContributionEvidenceRef = text(profileContributionEvidenceRef, "profileContributionEvidenceRef");
        policyContributionEvidenceRef = text(policyContributionEvidenceRef, "policyContributionEvidenceRef");
        requestedProfile = optional(requestedProfile);
        materialType = optional(materialType);
    }

    private static String text(String value, String name) {
        if (value == null || value.trim().isEmpty()) throw new IllegalArgumentException(name + " must not be blank");
        return value.trim();
    }
    private static String optional(String value) { return value == null || value.trim().isEmpty() ? null : value.trim(); }
}
