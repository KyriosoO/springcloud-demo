package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.time.Clock;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import org.junit.jupiter.api.Test;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.metadata.authorization.internal.AuthorizationPlanningPortImpl;
import com.dylan.agent.metadata.authorization.internal.UserPermissionBoundary;
import com.dylan.agent.metadata.authorization.model.DelegationConstraintRef;
import com.dylan.agent.metadata.authorization.resource.CapabilityResourceLimitResolver;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.authorization.request.CapabilityScopeSelection;
import com.dylan.agent.metadata.authorization.request.PlanningSecurityRequest;
import com.dylan.agent.metadata.config.AgentMetadataStore;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;
import com.dylan.agent.metadata.domain.port.DomainMetadataReferenceSet;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.policy.model.DomainSecurityConstraints;
import com.dylan.agent.metadata.profile.internal.EffectiveProfileCalculator;
import com.dylan.agent.metadata.profile.model.AgentProfileVersionKey;
import com.dylan.agent.metadata.profile.model.EffectiveProfile;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.shared.ref.AgentProfileRef;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;
import com.dylan.agent.testsupport.KernelTestSupport;

class AuthorizationPlanningPortTest {
    @Test
    void captureIntersectsProfilePolicyPermissionAndDelegation() {
        var port = new AuthorizationPlanningPortImpl(
                new AgentMetadataStore(MetadataTestSupport.bundle("bundle-v1", "digest-v1")),
                new EffectiveProfileCalculator(),
                new UserPermissionBoundary((subject, deadline) -> MetadataTestSupport.permission(subject),
                        Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC)),
                resourceLimitResolver(),
                DomainMetadataTestSupport.domainMetadataPort(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        var evidence = port.capture(new PlanningSecurityRequest(handle(), handle().agentProfileRef(),
                DelegationConstraintRef.CHAT_ALL));

        assertThat(evidence.planningScope().allowedCapabilityIds()).containsExactly("query.search");
        assertThat(evidence.planningScope().allowedDomains()).containsExactly("employee");
    }

    @Test
    void planningScopeIncludesQueryPreviewOnlyWhenPermissionAllows() {
        var port = new AuthorizationPlanningPortImpl(
                new AgentMetadataStore(MetadataTestSupport.bundleWithQueryPreview("bundle-v1", "digest-v1")),
                new EffectiveProfileCalculator(),
                new UserPermissionBoundary((subject, deadline) -> MetadataTestSupport.permissionWithQueryPreview(subject),
                        Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC)),
                resourceLimitResolver(),
                DomainMetadataTestSupport.domainMetadataPort(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        var evidence = port.capture(new PlanningSecurityRequest(handle(), handle().agentProfileRef(),
                DelegationConstraintRef.CHAT_ALL));

        assertThat(evidence.planningScope().allowedCapabilityIds())
                .containsExactlyInAnyOrder("query.search", "query.preview", "aggregate.compute");
        assertThat(evidence.planningScope().allowedDomains())
                .containsExactlyInAnyOrder("employee", "transaction");
    }

    @Test
    void planningScopeExcludesQueryPreviewWhenPermissionDoesNotAllowIt() {
        var port = new AuthorizationPlanningPortImpl(
                new AgentMetadataStore(MetadataTestSupport.bundleWithQueryPreview("bundle-v1", "digest-v1")),
                new EffectiveProfileCalculator(),
                new UserPermissionBoundary((subject, deadline) -> MetadataTestSupport.permission(subject),
                        Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC)),
                resourceLimitResolver(),
                DomainMetadataTestSupport.domainMetadataPort(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        var evidence = port.capture(new PlanningSecurityRequest(handle(), handle().agentProfileRef(),
                DelegationConstraintRef.CHAT_ALL));

        assertThat(evidence.planningScope().allowedCapabilityIds()).containsExactly("query.search");
        assertThat(evidence.planningScope().allowedDomains()).containsExactly("employee");
    }

    @Test
    void capturesPolicyRequiredMaskInPlanningScope() {
        var field = new CanonicalFieldRef("employee", "chineseName");
        var port = planningPortWithFieldSecurity(Map.of(field, fieldConstraint(MaskType.MOBILE)));

        var evidence = port.capture(new PlanningSecurityRequest(handle(), handle().agentProfileRef(),
                DelegationConstraintRef.CHAT_ALL));

        assertThat(evidence.planningScope().fieldAccess().get(field).requiredMask())
                .contains(MaskType.MOBILE);
    }

    @Test
    void freezesNonNoneFieldMasksInAuthorizationSnapshot() {
        var field = new CanonicalFieldRef("employee", "chineseName");
        var port = planningPortWithFieldSecurity(Map.of(field, fieldConstraint(MaskType.MOBILE)));
        var evidence = port.capture(new PlanningSecurityRequest(handle(), handle().agentProfileRef(),
                DelegationConstraintRef.CHAT_ALL));

        var snapshot = port.freezeCapabilityScope(evidence, new CapabilityScopeSelection(
                KernelTestSupport.resolvedQueryRegistration(),
                Optional.of("employee"),
                List.of(),
                evidence.domainMetadataEvidence()));

        assertThat(snapshot.fieldMasks())
                .containsEntry("employee.chineseName", MaskType.MOBILE);
    }

    @Test
    void doesNotCreateMaskForUnauthorizedField() {
        var field = new CanonicalFieldRef("employee", "idCardNo");
        var port = planningPortWithFieldSecurity(Map.of(field, fieldConstraint(MaskType.ID_CARD)));
        var evidence = port.capture(new PlanningSecurityRequest(handle(), handle().agentProfileRef(),
                DelegationConstraintRef.CHAT_ALL));

        var snapshot = port.freezeCapabilityScope(evidence, new CapabilityScopeSelection(
                KernelTestSupport.resolvedQueryRegistration(),
                Optional.of("employee"),
                List.of(),
                evidence.domainMetadataEvidence()));

        assertThat(evidence.planningScope().fieldAccess())
                .doesNotContainKey(field);
        assertThat(snapshot.fieldMasks())
                .doesNotContainKey("employee.idCardNo");
    }

    @Test
    void freezesDocumentRetrievableBudgetWithPageSizeLimit() {
        DomainMetadataPort domainMetadataPort = DomainMetadataTestSupport.domainMetadataPort();
        var port = planningPort(domainMetadataPort);
        var evidence = documentPlanningEvidence(domainMetadataPort);

        var snapshot = port.freezeCapabilityScope(evidence, new CapabilityScopeSelection(
                KernelTestSupport.resolvedDocumentSearchRegistration(),
                Optional.of("company_policy"),
                List.of(),
                evidence.domainMetadataEvidence()));

        var limits = snapshot.resourceLimits().require(
                com.dylan.agent.api.contract.common.AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT,
                com.dylan.agent.adapter.api.document.DocumentResourceLimit.class);
        assertThat(limits.retrieval().maxReturnedDocuments()).isEqualTo(7);
    }

    private AuthorizationPlanningPortImpl planningPortWithFieldSecurity(
            Map<CanonicalFieldRef, DomainSecurityConstraints.FieldSecurityConstraint> fields) {
        return new AuthorizationPlanningPortImpl(
                new AgentMetadataStore(MetadataTestSupport.bundleWithEmployeeFieldSecurity(
                        "bundle-v1", "digest-v1", fields)),
                new EffectiveProfileCalculator(),
                new UserPermissionBoundary((subject, deadline) -> MetadataTestSupport.permission(subject),
                        Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC)),
                resourceLimitResolver(),
                DomainMetadataTestSupport.domainMetadataPort(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));
    }

    private AuthorizationPlanningPortImpl planningPort(DomainMetadataPort domainMetadataPort) {
        return new AuthorizationPlanningPortImpl(
                new AgentMetadataStore(MetadataTestSupport.bundle("bundle-v1", "digest-v1")),
                new EffectiveProfileCalculator(),
                new UserPermissionBoundary((subject, deadline) -> MetadataTestSupport.permission(subject),
                        Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC)),
                resourceLimitResolver(),
                domainMetadataPort,
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));
    }

    private PlanningAuthorizationEvidence documentPlanningEvidence(DomainMetadataPort domainMetadataPort) {
        AgentProfileVersionKey profileKey = new AgentProfileVersionKey("agent-default", "profile-v1");
        PlanningEffectiveScope planningScope = com.dylan.agent.testsupport.PlanningEffectiveScopeTestFactory.create(
                Set.of("document.search"),
                Set.of("company_policy"),
                Map.of(),
                Set.of(RuntimeContextType.DOCUMENT),
                Set.of(RuntimeContextType.DOCUMENT),
                AgentCapabilityRiskLevel.READ_ONLY,
                AgentCapabilityExecutionMode.IMMEDIATE,
                Duration.ofSeconds(30),
                1,
                7,
                100,
                10_000);
        EffectiveProfile effectiveProfile = new EffectiveProfile(
                profileKey,
                "policy-v1",
                planningScope.allowedCapabilityIds(),
                planningScope.allowedDomains(),
                planningScope.readableContextTypes(),
                planningScope.writableContextTypes(),
                planningScope.maxRiskLevel(),
                planningScope.maxExecutionMode(),
                planningScope.planningBudgetLimits(),
                planningScope.resourceLimitContributions());
        return com.dylan.agent.testsupport.PlanningAuthorizationEvidenceTestFactory.create(
                "corr-1",
                "user:u-1",
                profileKey,
                "bundle-v1",
                "digest-v1",
                "policy-v1",
                "perm-evidence",
                "perm-v1",
                DelegationConstraintRef.CHAT_ALL,
                effectiveProfile,
                planningScope,
                domainMetadataPort.validateReferences(DomainMetadataReferenceSet.empty(),
                        MetadataTestSupport.NOW.plusSeconds(60)),
                MetadataTestSupport.NOW,
                MetadataTestSupport.NOW.plusSeconds(60));
    }

    private static DomainSecurityConstraints.FieldSecurityConstraint fieldConstraint(MaskType maskType) {
        return new DomainSecurityConstraints.FieldSecurityConstraint(
                true,
                true,
                Set.of(AgentOperator.EQ),
                Set.of(),
                Optional.of(maskType),
                new com.dylan.agent.metadata.policy.model.SecurityClassificationRef(
                        "test", "internal", "v1"),
                Set.of());
    }

    private static CapabilityResourceLimitResolver resourceLimitResolver() {
        return new CapabilityResourceLimitResolver(
                new com.dylan.agent.kernel.resource.CapabilityResourceLimitRegistry(List.of(
                        new com.dylan.agent.kernel.resource.StandardCapabilityResourceLimitContract(),
                        new com.dylan.agent.kernel.resource.DocumentCapabilityResourceLimitContract())));
    }

    private InvocationHandle handle() {
        return InvocationHandle.forChat(
                "inv-1",
                new ChatInvocationOrigin("conv-1", "turn-1"),
                "corr-1",
                new ExecutionSubjectRef("user", "u-1"),
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                AgentProfileRef.of("agent-default", "profile-v1"),
                MetadataTestSupport.NOW.plusSeconds(60));
    }
}
