package com.dylan.agent.testsupport;

import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.metadata.authorization.model.DelegationConstraintRef;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.metadata.profile.model.AgentProfileVersionKey;
import com.dylan.agent.metadata.profile.model.EffectiveProfile;
import com.dylan.agent.shared.ref.AgentProfileRef;

import java.time.Duration;
import java.time.Instant;

/** 生成绑定 invocation、owner、conversation 与 exact profile 的规划授权证据。 */
public final class PlanningAuthorizationEvidenceTestFactory {
    private PlanningAuthorizationEvidenceTestFactory() {
    }

    public static PlanningAuthorizationEvidence create(
            String requestCorrelationId,
            String subjectRef,
            AgentProfileVersionKey profileKey,
            String metadataBundleVersion,
            String metadataBundleDigest,
            String policyVersion,
            String permissionEvidenceId,
            String permissionVersion,
            DelegationConstraintRef delegationConstraintRef,
            EffectiveProfile effectiveProfile,
            PlanningEffectiveScope planningScope,
            DomainMetadataEvidence domainMetadataEvidence,
            Instant capturedAt,
            Instant absoluteDeadline) {
        String[] subject = subjectRef.split(":", 2);
        return new PlanningAuthorizationEvidence(
                "inv-1",
                requestCorrelationId,
                new ExecutionSubjectRef(subject[0], subject[1]),
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                AgentProfileRef.of(profileKey.agentId(), profileKey.version()),
                profileKey,
                metadataBundleVersion,
                metadataBundleDigest,
                policyVersion,
                permissionEvidenceId,
                permissionVersion,
                delegationConstraintRef,
                effectiveProfile,
                planningScope,
                domainMetadataEvidence,
                Duration.ofHours(1),
                capturedAt,
                absoluteDeadline);
    }
}
