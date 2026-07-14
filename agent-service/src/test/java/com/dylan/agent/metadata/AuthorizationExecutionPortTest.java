package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Clock;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.Test;

import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.metadata.authorization.internal.AuthorizationExecutionPortImpl;
import com.dylan.agent.metadata.authorization.internal.UserPermissionBoundary;
import com.dylan.agent.metadata.authorization.model.AuthorizationSnapshot;
import com.dylan.agent.metadata.authorization.model.UserPermission;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.shared.ref.AgentProfileRef;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

class AuthorizationExecutionPortTest {
    @Test
    void recheckNeverExpandsSnapshot() {
        AuthorizationExecutionPortImpl port = port(MetadataTestSupport::permission);
        var snapshot = snapshot();
        var scope = port.recheck(snapshot, handle());

        assertThat(scope.allowedCapabilityIds()).containsExactly("query.search");
        assertThat(scope.allowedDomains()).containsExactly("employee");
        var limits = com.dylan.agent.kernel.resource.StandardResourceLimits.require(scope);
        assertThat(limits.maxPageSize()).isEqualTo(100);
        assertThat(limits.maxResultRows()).isEqualTo(100);
        assertThat(limits.maxResultBytes()).isEqualTo(10_000);
        assertThat(scope.resourceLimits()).isNotSameAs(snapshot.resourceLimits());
        assertThat(scope.resourceLimits().bindingIdentity())
                .isEqualTo(snapshot.resourceLimits().bindingIdentity());
    }

    @Test
    void passesSnapshotFieldMasksToExecutionScope() {
        AuthorizationExecutionPortImpl port = port(MetadataTestSupport::permission);

        var scope = port.recheck(snapshot(Map.of("employee.chineseName", MaskType.MOBILE)), handle());

        assertThat(scope.fieldMasks())
                .containsEntry("employee.chineseName", MaskType.MOBILE);
    }

    @Test
    void acceptsNewPermissionEvidenceWhenItStillCoversFrozenScope() {
        AuthorizationExecutionPortImpl port = port(subject -> permissionWithNewEvidence(subject));

        var scope = port.recheck(snapshot(), handle());

        assertThat(scope.currentPermissionEvidenceId()).isEqualTo("permission-current");
        assertThat(scope.currentPermissionVersion()).isEqualTo("permission-v2");
        assertThat(scope.allowedCapabilityIds()).containsExactly("query.search");
    }

    @Test
    void recheckRejectsCurrentPermissionThatNoLongerCoversSnapshotFields() {
        AuthorizationExecutionPortImpl port = port(this::permissionWithoutFields);

        assertThatThrownBy(() -> port.recheck(snapshot(), handle()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("permission recheck would shrink required scope");
    }

    @Test
    void recheckRejectsCurrentPermissionThatLostDisplayFieldEvenWhenFilterRemains() {
        AuthorizationExecutionPortImpl port = port(this::permissionWithoutDisplayField);

        assertThatThrownBy(() -> port.recheck(snapshot(), handle()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("permission recheck would shrink required scope");
    }

    private AuthorizationSnapshot snapshot() {
        return snapshot(Map.of());
    }

    private AuthorizationExecutionPortImpl port(
            java.util.function.Function<ExecutionSubjectRef, UserPermission> permissionResolver) {
        Clock clock = Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC);
        return new AuthorizationExecutionPortImpl(
                new UserPermissionBoundary((subject, deadline) -> permissionResolver.apply(subject), clock),
                new com.dylan.agent.metadata.config.AgentMetadataStore(
                        MetadataTestSupport.bundle("bundle-v1", "digest-v1")),
                DomainMetadataTestSupport.domainMetadataPort(),
                new com.dylan.agent.metadata.authorization.resource.CapabilityResourceLimitResolver(
                        com.dylan.agent.kernel.resource.StandardResourceLimits.registry()),
                clock);
    }

    private AuthorizationSnapshot snapshot(Map<String, MaskType> fieldMasks) {
        DomainMetadataEvidence evidence = DomainMetadataTestSupport.currentEvidence();
        return com.dylan.agent.testsupport.AuthorizationSnapshotTestFactory.create(
                "auth-1", "user:u-1", "profile-v1", "policy-v1",
                Set.of("query.search"), Set.of("employee"),
                Map.of("employee", Set.of("chineseName")),
                fieldMasks,
                MetadataTestSupport.NOW, evidence,
                com.dylan.agent.kernel.resource.StandardResourceLimits.testEffective(100, 100, 10_000));
    }

    private UserPermission permissionWithoutFields(ExecutionSubjectRef subject) {
        UserPermission permission = MetadataTestSupport.permission(subject);
        return new UserPermission(
                subject,
                permission.evidenceId(),
                permission.version(),
                permission.allowedCapabilityIds(),
                permission.allowedDomains(),
                Map.of("employee", Set.of()),
                Map.of("employee", Set.of()),
                permission.allowedOperators(),
                permission.allowedFunctions(),
                permission.readableContextTypes(),
                permission.writableContextTypes(),
                permission.attributes(),
                permission.resolvedAt());
    }

    private UserPermission permissionWithNewEvidence(ExecutionSubjectRef subject) {
        UserPermission permission = MetadataTestSupport.permission(subject);
        return new UserPermission(
                subject,
                "permission-current",
                "permission-v2",
                permission.allowedCapabilityIds(),
                permission.allowedDomains(),
                permission.filterableFields(),
                permission.displayableFields(),
                permission.allowedOperators(),
                permission.allowedFunctions(),
                permission.readableContextTypes(),
                permission.writableContextTypes(),
                permission.attributes(),
                permission.resolvedAt());
    }

    private UserPermission permissionWithoutDisplayField(ExecutionSubjectRef subject) {
        UserPermission permission = MetadataTestSupport.permission(subject);
        return new UserPermission(
                subject,
                permission.evidenceId(),
                permission.version(),
                permission.allowedCapabilityIds(),
                permission.allowedDomains(),
                Map.of("employee", Set.of()),
                Map.of("employee", Set.of("chineseName")),
                permission.allowedOperators(),
                permission.allowedFunctions(),
                permission.readableContextTypes(),
                permission.writableContextTypes(),
                permission.attributes(),
                permission.resolvedAt());
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
