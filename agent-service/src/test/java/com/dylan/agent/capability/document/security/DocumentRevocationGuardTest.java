package com.dylan.agent.capability.document.security;

import com.dylan.agent.adapter.api.document.*;
import com.dylan.agent.adapter.api.operation.*;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.acl.*;
import com.dylan.agent.capability.document.governance.emergency.*;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.kernel.core.DocumentCapabilityHandlerTestSupport;
import org.junit.jupiter.api.Test;

import java.time.*;
import java.util.*;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentRevocationGuardTest {
    private static final Instant NOW = Instant.parse("2026-07-14T00:00:00Z");

    @Test
    void allowsOnlyWhenAclCandidatesAndEmergencyViewAreCurrent() {
        DocumentRevocationGuard guard = guard(allowCurrentness(), allowingEmergency());

        DocumentFinalCurrentnessDecision decision = guard.evaluate(request());

        assertThat(decision.outcome()).isEqualTo(DocumentCurrentnessOutcome.ALLOW);
        assertThat(decision.reasonCode()).isEqualTo(DocumentSecurityReasonCode.CURRENT);
        assertThat(decision.validUntil()).isEqualTo(NOW.plusSeconds(2));
    }

    @Test
    void deniesWholeResultWhenAnyCandidateIsRevoked() {
        DocumentAclCurrentnessPort currentness = new StubCurrentness(DocumentCurrentnessOutcome.DENY);

        DocumentFinalCurrentnessDecision decision = guard(currentness, allowingEmergency()).evaluate(request());

        assertThat(decision.outcome()).isEqualTo(DocumentCurrentnessOutcome.DENY);
        assertThat(decision.reasonCode()).isEqualTo(DocumentSecurityReasonCode.ACL_DENIED);
    }

    @Test
    void deniesWholeResultWhenEmergencyStateBlocksTarget() {
        DocumentEmergencyControlReadPort emergency = (targets, deadline) -> new DocumentEmergencyView(
                "view-1", List.of(new DocumentEmergencyView.Decision(
                "CORPUS", "a".repeat(64), DocumentEmergencyView.Outcome.BLOCKED, "EMERGENCY_ACTIVE")),
                NOW, NOW.plusSeconds(2), "b".repeat(64));

        DocumentFinalCurrentnessDecision decision = guard(allowCurrentness(), emergency).evaluate(request());

        assertThat(decision.outcome()).isEqualTo(DocumentCurrentnessOutcome.DENY);
        assertThat(decision.reasonCode()).isEqualTo(DocumentSecurityReasonCode.EMERGENCY_BLOCKED);
    }

    private static DocumentRevocationGuard guard(
            DocumentAclCurrentnessPort currentness,
            DocumentEmergencyControlReadPort emergency) {
        return new DocumentRevocationGuard(currentness, emergency, Clock.fixed(NOW, ZoneOffset.UTC), Duration.ofSeconds(2));
    }

    private static DocumentAclCurrentnessPort allowCurrentness() {
        return new StubCurrentness(DocumentCurrentnessOutcome.ALLOW);
    }

    private static DocumentEmergencyControlReadPort allowingEmergency() {
        return (targets, deadline) -> new DocumentEmergencyView(
                "view-1", targets.stream().map(target -> new DocumentEmergencyView.Decision(
                target.type(), "a".repeat(64), DocumentEmergencyView.Outcome.NOT_BLOCKED, null)).toList(),
                NOW, NOW.plusSeconds(2), "b".repeat(64));
    }

    private static DocumentRevocationGuard.FinalDocumentCurrentnessRequest request() {
        DocumentAclExecutionEvidence evidence = evidence();
        DocumentCandidateSecurityBinding binding = new DocumentCandidateSecurityBinding(
                "inv-1", "corr-1", "document-reg", evidence.corpusKey(),
                new DocumentTargetBindingReference("3.0.0", "e".repeat(64), "f".repeat(64), "1".repeat(64)),
                "2".repeat(64), evidence.canonicalDigest(), new DocumentAclObjectRef("acl-1", "acl-v1"),
                evidence.profileProjectionDigest(), reference());
        SafeDocumentCandidate candidate = new SafeDocumentCandidate(
                "candidate-1", new DocumentCandidateIdentity("doc-1", "v1", "chunk-1", 0),
                "政策", null, null, "证据", null, null, List.of(), List.of("BM25"), 1.0, binding);
        return new DocumentRevocationGuard.FinalDocumentCurrentnessRequest(
                evidence, List.of(candidate), "9".repeat(64), "agent-default:profile-v1", context());
    }

    private static DocumentAclExecutionEvidence evidence() {
        return new DocumentAclExecutionEvidence(
                "inv-1", "corr-1", "document-reg", new ExecutionSubjectRef("user", "u-1"),
                new DocumentCorpusKey("policy", "document"), DocumentPlanOperation.SEARCH,
                new PermissionEvidenceReference("perm-evidence", "perm-v1"), "acl-v1",
                "3".repeat(64), "4".repeat(64), "5".repeat(64), reference(),
                NOW.minusSeconds(1), NOW.plusSeconds(30), "6".repeat(64));
    }

    private static CapabilityOperationContext context() {
        return new CapabilityOperationContext(
                "inv-1", "corr-1", "document.search", "op-final",
                CapabilityOperationType.of("DOCUMENT_ACL_CANDIDATE_CURRENTNESS"), NOW.plusSeconds(5), () -> false,
                DocumentCapabilityHandlerTestSupport.executionScope().resourceLimits());
    }

    private static ResourceLimitReference reference() {
        return DocumentCapabilityHandlerTestSupport.executionScope().resourceLimits().reference();
    }

    private record StubCurrentness(DocumentCurrentnessOutcome outcome) implements DocumentAclCurrentnessPort {
        @Override public DocumentAclCurrentnessDecision verifyScope(DocumentAclScopeCurrentnessRequest request) {
            return decision(request.operationContext());
        }
        @Override public DocumentAclCurrentnessDecision verifyCandidates(DocumentAclCandidateCurrentnessRequest request) {
            return decision(request.operationContext());
        }
        private DocumentAclCurrentnessDecision decision(CapabilityOperationContext context) {
            var metadata = new CapabilityOperationMetadata(
                    context.operationId(), context.operationType(), new ProviderSafeIdentity("acl", Optional.empty()),
                    1, 1, outcome == DocumentCurrentnessOutcome.ALLOW
                    ? CapabilityOperationTermination.SUCCEEDED : CapabilityOperationTermination.REJECTED,
                    "diagnostic", context.resourceLimits().reference(), false, false, false);
            return new DocumentAclCurrentnessDecision(
                    outcome, "acl-v1", "perm-v1", "decision-v1", NOW, NOW.plusSeconds(2),
                    outcome.name(), metadata);
        }
    }
}
