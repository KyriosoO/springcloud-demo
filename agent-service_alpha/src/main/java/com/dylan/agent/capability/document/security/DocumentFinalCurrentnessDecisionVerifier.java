package com.dylan.agent.capability.document.security;

import com.dylan.agent.capability.document.acl.DocumentCurrentnessOutcome;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

import java.time.Clock;
import java.util.Objects;

/** Result Security 内纯本地校验；不得发起 authority/governance I/O。 */
public final class DocumentFinalCurrentnessDecisionVerifier {
    private final Clock clock;
    public DocumentFinalCurrentnessDecisionVerifier(Clock clock){this.clock=Objects.requireNonNull(clock);}
    public void verify(DocumentFinalCurrentnessDecision decision,String candidateSetDigest,ExecutionScope scope){
        Objects.requireNonNull(decision,"final currentness decision required");
        if(decision.outcome()!= DocumentCurrentnessOutcome.ALLOW
                || !decision.invocationId().equals(scope.invocationId())
                || !decision.permissionVersion().equals(scope.currentPermissionVersion())
                || !decision.candidateSetDigest().equals(candidateSetDigest)
                || !decision.authorizationBindingDigest().equals(scope.resourceLimits().reference().canonicalDigest())
                || !decision.resourceLimitReference().equals(scope.resourceLimits().reference())
                || decision.checkedAt().isAfter(clock.instant()) || !decision.validUntil().isAfter(clock.instant())){
            throw new IllegalStateException("document final currentness decision binding/expiry invalid");
        }
        String expected=DocumentFinalDecisionDigests.digest(decision.outcome(),decision.invocationId(),decision.operationId(),
                decision.permissionVersion(),decision.candidateSetDigest(),decision.authorizationBindingDigest(),
                decision.resourceLimitReference().canonicalDigest(),decision.aclDecisionVersion(),decision.emergencyViewVersion(),
                decision.checkedAt(),decision.validUntil(),decision.reasonCode());
        if(!expected.equals(decision.decisionDigest()))throw new IllegalStateException("document final decision digest mismatch");
    }
}
