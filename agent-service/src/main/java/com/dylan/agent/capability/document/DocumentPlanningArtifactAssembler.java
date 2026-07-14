package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.DocumentResourceLimit;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.plan.AgentPlan;
import com.dylan.agent.api.contract.runtime.plan.DocumentAgentPlan;
import com.dylan.agent.capability.document.profile.DocumentPlanningProfileProjector;
import com.dylan.agent.capability.document.profile.DocumentProfileProjectionDigest;
import com.dylan.agent.capability.document.profile.DocumentProfileSelection;
import com.dylan.agent.capability.document.profile.DocumentProfileSelectionCommand;
import com.dylan.agent.capability.document.profile.DocumentRetrievalProfileResolver;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.metadata.authorization.model.AuthorizationSnapshot;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.authorization.resource.ResourceLimitSource;
import com.dylan.agent.planning.PlanningArtifactAssembler;
import com.dylan.agent.planning.ValidatedRouteDecision;
import com.dylan.agent.planning.model.PlanningCommand;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.Objects;

/** Route 后 exact Profile 选择、freeze 后唯一 projection 和 RawPlan 绑定 seam。 */
public final class DocumentPlanningArtifactAssembler implements PlanningArtifactAssembler {
    private final DocumentRetrievalProfileResolver profiles;
    private final DocumentPlanningProfileProjector projector;
    private final ObjectMapper mapper;

    public DocumentPlanningArtifactAssembler(
            DocumentRetrievalProfileResolver profiles,
            DocumentPlanningProfileProjector projector,
            ObjectMapper mapper) {
        this.profiles = Objects.requireNonNull(profiles);
        this.projector = Objects.requireNonNull(projector);
        this.mapper = Objects.requireNonNull(mapper);
    }

    @Override
    public PreparedBinding prepare(
            PlanningCommand command,
            PlanningAuthorizationEvidence evidence,
            ValidatedRouteDecision route,
            ResolvedRegistration registration) {
        if (registration.planKind() != AgentPlanKind.DOCUMENT) return new IdentityBinding();
        String domain = route.domain().orElseThrow(() -> new IllegalArgumentException("DOCUMENT domain required"));
        var contributions = evidence.planningScope().resourceLimitContributions();
        var profileContribution = contributions.require(ResourceLimitSource.PROFILE,
                AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, DocumentResourceLimit.class);
        var policyContribution = contributions.require(ResourceLimitSource.POLICY,
                AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, DocumentResourceLimit.class);
        DocumentProfileSelection selection = profiles.select(new DocumentProfileSelectionCommand(
                registration.capabilityId(), domain, DocumentPlanningProfileProjector.operation(registration.capabilityId()),
                evidence.agentProfileRef(), evidence.policyVersion(), evidence,
                profileContribution.evidenceRef(), policyContribution.evidenceRef(),
                command.requestedProfile(), command.materialType()));
        return new DocumentPreparedBinding(
                command.handle().invocationId(), command.handle().requestCorrelationId(),
                registration.registrationIdentity(), evidence.agentProfileRef(), registration.capabilityId(), selection);
    }

    @Override
    public FrozenBinding freeze(PreparedBinding prepared, AuthorizationSnapshot authorizationSnapshot) {
        if (prepared instanceof IdentityBinding) return new IdentityFrozenBinding();
        if (!(prepared instanceof DocumentPreparedBinding binding)) {
            throw new IllegalArgumentException("document prepared binding mismatch");
        }
        DocumentResourceLimit limits = authorizationSnapshot.resourceLimits().require(
                AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, DocumentResourceLimit.class);
        var projection = projector.project(binding.selection(), limits, binding.capabilityId());
        if (!projection.profileName().equals(binding.selection().selectedProfileName())
                || !projection.documentProfileVersion().equals(binding.selection().assetRef().documentProfileVersion())) {
            throw new IllegalStateException("document final projection does not bind selected profile");
        }
        String digest = DocumentProfileProjectionDigest.compute(projection);
        DocumentProfileBinding profileBinding = new DocumentProfileBinding(
                binding.invocationId(), binding.requestCorrelationId(), binding.registrationIdentity(),
                binding.agentProfileRef(), projection.documentProfileVersion(),
                authorizationSnapshot.resourceLimits().reference(), digest);
        return new DocumentFrozenBinding(profileBinding, projection);
    }

    @Override
    public AgentPlan assemble(AgentPlan runtimePlan, FrozenBinding frozen) {
        if (frozen instanceof IdentityFrozenBinding) return runtimePlan;
        if (!(frozen instanceof DocumentFrozenBinding binding) || !(runtimePlan instanceof DocumentAgentPlan document)) {
            throw new IllegalArgumentException("document frozen binding/raw plan mismatch");
        }
        return new DocumentRawPlan(document, binding.profileBinding(), binding.projection(), mapper);
    }

    private record DocumentPreparedBinding(
            String invocationId,
            String requestCorrelationId,
            String registrationIdentity,
            com.dylan.agent.shared.ref.AgentProfileRef agentProfileRef,
            String capabilityId,
            DocumentProfileSelection selection) implements PreparedBinding {}

    private record DocumentFrozenBinding(
            DocumentProfileBinding profileBinding,
            com.dylan.agent.capability.document.profile.DocumentPlanningProfileProjection projection)
            implements FrozenBinding {}
}
