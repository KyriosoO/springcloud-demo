package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import org.junit.jupiter.api.Test;

import com.dylan.agent.kernel.port.model.SecuredResult;

class MetadataArchitectureTest {

    @Test
    void d0203PlannedProductionFilesExist() {
        Path root = Path.of("src/main/java/com/dylan/agent");
        List<String> expected = List.of(
                "metadata/profile/model/AgentProfileDefinition.java",
                "metadata/profile/model/AgentProfileVersionKey.java",
                "metadata/profile/model/ProfileBehaviorAsset.java",
                "metadata/profile/model/ProfileBehaviorAssetRef.java",
                "metadata/profile/internal/AgentProfileRegistry.java",
                "metadata/profile/internal/ProfileBehaviorProjectionBoundary.java",
                "metadata/profile/model/EffectiveProfile.java",
                "metadata/profile/internal/EffectiveProfileCalculator.java",
                "metadata/config/AgentMetadataBundle.java",
                "metadata/config/AgentSecuritySettings.java",
                "metadata/config/AgentSecuritySettingsRegistry.java",
                "metadata/config/AgentMetadataStore.java",
                "metadata/config/AgentMetadataReloader.java",
                "metadata/config/AgentMetadataBootstrap.java",
                "metadata/config/AgentMetadataRefreshListener.java",
                "metadata/policy/model/AgentPolicySnapshot.java",
                "metadata/policy/model/ProfileConstraints.java",
                "metadata/policy/model/CapabilityConstraints.java",
                "metadata/policy/model/DomainSecurityConstraints.java",
                "metadata/policy/model/BudgetLimits.java",
                "metadata/policy/model/DelegationLimits.java",
                "metadata/policy/model/EmergencyRevocation.java",
                "metadata/policy/model/EmergencyRevocationTarget.java",
                "metadata/policy/internal/AgentPolicyConfiguration.java",
                "metadata/authorization/model/UserPermission.java",
                "metadata/authorization/port/UserPermissionAuthorityPort.java",
                "metadata/authorization/port/UserPermissionAuthorityFailure.java",
                "metadata/authorization/port/UserPermissionAuthorityException.java",
                "metadata/authorization/internal/UserPermissionBoundary.java",
                "metadata/authorization/internal/AuthorizationSecurityConfiguration.java",
                "metadata/authorization/model/DelegationConstraintRef.java",
                "metadata/authorization/model/DelegationConstraint.java",
                "metadata/authorization/internal/DelegationBoundary.java",
                "metadata/authorization/model/PlanningAuthorizationEvidence.java",
                "metadata/authorization/model/PlanningEffectiveScope.java",
                "metadata/authorization/request/PlanningSecurityRequest.java",
                "metadata/authorization/request/CapabilityScopeSelection.java",
                "metadata/authorization/model/AuthorizationSnapshot.java",
                "metadata/authorization/model/ExecutionScope.java",
                "metadata/authorization/port/AuthorizationPlanningPort.java",
                "metadata/authorization/internal/AuthorizationPlanningPortImpl.java",
                "metadata/authorization/internal/AuthorizationExecutionPortImpl.java",
                "metadata/catalog/CapabilityCatalog.java",
                "metadata/catalog/AvailableCapability.java",
                "metadata/catalog/AvailableCapabilitySnapshot.java",
                "metadata/domain/port/DomainMetadataPort.java",
                "metadata/domain/port/CanonicalFieldRef.java",
                "metadata/domain/port/CanonicalOperatorRef.java",
                "metadata/domain/port/CanonicalFunctionRef.java",
                "metadata/domain/port/DomainMetadataReferenceSet.java",
                "metadata/domain/port/DomainAvailabilitySnapshot.java",
                "metadata/domain/port/DomainMetadataEvidence.java",
                "metadata/domain/DomainSecurityBoundary.java",
                "metadata/context/model/ContextRecordKey.java",
                "metadata/context/model/CapabilityContextEnvelope.java",
                "metadata/context/model/ContextSnapshot.java",
                "metadata/context/model/ContextWriteCandidate.java",
                "metadata/context/request/ContextReadRequest.java",
                "metadata/context/port/ContextPlanningPort.java",
                "metadata/context/internal/ContextBoundary.java",
                "metadata/context/internal/ContextRepository.java",
                "metadata/context/internal/ContextRecordEntity.java",
                "metadata/context/internal/ContextRecordMapper.java",
                "metadata/context/internal/ContextFinalizationParticipantImpl.java",
                "metadata/context/internal/ContextScopeRetirementParticipantImpl.java",
                "metadata/context/internal/ContextCleanupJob.java",
                "metadata/context/migration/ContextPayloadMigrator.java",
                "metadata/context/migration/ContextMigrationRegistry.java",
                "metadata/crypto/model/ProtectedPayload.java",
                "metadata/crypto/model/PayloadProtectionContext.java",
                "metadata/crypto/port/ProtectedPayloadCodec.java",
                "metadata/crypto/model/PayloadPurpose.java",
                "metadata/crypto/port/PayloadKeyProvider.java",
                "metadata/crypto/internal/AeadProtectedPayloadCodec.java",
                "metadata/crypto/internal/EnvironmentPayloadKeyProvider.java",
                "metadata/crypto/internal/PayloadJsonCodec.java",
                "metadata/result/FilteredResult.java",
                "metadata/result/ResultSecurityProjector.java",
                "metadata/result/ResultSecurityProjectorRegistry.java",
                "metadata/result/ResultSecurityBoundary.java",
                "metadata/result/QueryResultSecurityProjector.java",
                "metadata/result/AggregateResultSecurityProjector.java",
                "metadata/config/AgentMetadataProperties.java",
                "metadata/config/AgentMetadataPropertiesValidator.java");

        assertThat(expected)
                .allSatisfy(relative -> assertThat(Files.exists(root.resolve(relative)))
                        .as(relative)
                        .isTrue());
    }

    @Test
    void securedResultDoesNotExposeTypedCandidatePayload() {
        assertThat(List.of(SecuredResult.class.getDeclaredMethods()).stream()
                        .map(Method::getName))
                .doesNotContain("candidateResult");
    }
}
