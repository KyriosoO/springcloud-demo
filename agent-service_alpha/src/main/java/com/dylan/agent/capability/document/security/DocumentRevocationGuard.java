package com.dylan.agent.capability.document.security;

import com.dylan.agent.adapter.api.document.SafeDocumentCandidate;
import com.dylan.agent.adapter.api.document.DocumentResourceLimit;
import com.dylan.agent.adapter.api.operation.CapabilityOperationContext;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.capability.document.acl.*;
import com.dylan.agent.capability.document.governance.emergency.*;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/** ACL candidate currentness 与 07 emergency view 的唯一 final decision 算法。 */
public final class DocumentRevocationGuard {
    private final DocumentAclCurrentnessPort currentness;
    private final DocumentEmergencyControlReadPort emergency;
    private final Clock clock;
    private final Duration finalDecisionMaxAge;
    private final int maxCurrentnessCandidates;
    private final DocumentCandidateSetCanonicalizer candidateSetCanonicalizer =
            new DocumentCandidateSetCanonicalizer();

    public DocumentRevocationGuard(
            DocumentAclCurrentnessPort currentness,
            DocumentEmergencyControlReadPort emergency,
            Clock clock,
            Duration finalDecisionMaxAge,
            DocumentAclCompilerLimits limits) {
        this.currentness=Objects.requireNonNull(currentness);
        this.emergency=Objects.requireNonNull(emergency);
        this.clock=Objects.requireNonNull(clock);
        this.finalDecisionMaxAge=Objects.requireNonNull(finalDecisionMaxAge);
        this.maxCurrentnessCandidates=Objects.requireNonNull(limits).maxCurrentnessCandidates();
        if(finalDecisionMaxAge.isZero()||finalDecisionMaxAge.isNegative())throw new IllegalArgumentException("finalDecisionMaxAge must be positive");
    }

    public DocumentFinalCurrentnessDecision evaluate(FinalDocumentCurrentnessRequest request){
        CapabilityOperationContext context=request.operationContext();
        if(context.cancellation().isCancelled())return deny(request,null,null,DocumentSecurityReasonCode.CANCELLED);
        if(!context.absoluteDeadline().isAfter(clock.instant()))return deny(request,null,null,DocumentSecurityReasonCode.DEADLINE_EXCEEDED);
        var evidence=request.evidence();
        var effectiveReference=context.resourceLimits().reference();
        DocumentResourceLimit resourceLimit = context.resourceLimits().require(
                AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, DocumentResourceLimit.class);
        int candidateCap = Math.min(maxCurrentnessCandidates,
                Math.min(resourceLimit.retrieval().maxReturnedDocuments(),
                        resourceLimit.output().maxEvidenceCount()));
        if (request.candidates().size() > candidateCap
                || !candidateSetCanonicalizer.digest(
                        request.candidates(), request.evidenceRefs(), request.outputContract())
                .equals(request.candidateSetDigest())) {
            return deny(request,null,null,DocumentSecurityReasonCode.CANDIDATE_BINDING_MISMATCH);
        }
        if(!context.invocationId().equals(evidence.invocationId())
                ||!context.requestCorrelationId().equals(evidence.requestCorrelationId())
                ||!effectiveReference.equals(evidence.resourceLimitReference())
                ||!effectiveReference.invocationId().equals(context.invocationId())
                ||!effectiveReference.registrationIdentity().equals(evidence.registrationIdentity())
                ||!evidence.expiresAt().isAfter(clock.instant())){
            return deny(request,null,null,DocumentSecurityReasonCode.CANDIDATE_BINDING_MISMATCH);
        }
        com.dylan.agent.adapter.api.document.DocumentTargetBindingReference targetBinding=null;
        String protectedFilterDigest=null;
        for(SafeDocumentCandidate candidate:request.candidates()){
            var binding=candidate.securityBinding();
            if(!binding.invocationId().equals(evidence.invocationId())
                    ||!binding.requestCorrelationId().equals(evidence.requestCorrelationId())
                    ||!binding.registrationIdentity().equals(evidence.registrationIdentity())
                    ||!binding.corpusKey().equals(evidence.corpusKey())
                    ||!binding.aclEvidenceDigest().equals(evidence.canonicalDigest())
                    ||!binding.profileProjectionDigest().equals(evidence.profileProjectionDigest())
                    ||!binding.resourceLimitReference().equals(effectiveReference)
                    ||targetBinding!=null&&!targetBinding.equals(binding.targetBinding())
                    ||protectedFilterDigest!=null&&!protectedFilterDigest.equals(binding.protectedFilterDigest())){
                return deny(request,null,null,DocumentSecurityReasonCode.CANDIDATE_BINDING_MISMATCH);
            }
            targetBinding=binding.targetBinding();
            protectedFilterDigest=binding.protectedFilterDigest();
        }
        var aclDecision=currentness.verifyCandidates(new DocumentAclCandidateCurrentnessRequest(
                request.evidence(),request.candidates().stream().map(c->c.securityBinding().aclObjectRef()).toList(),
                request.candidateSetDigest(),context));
        if(aclDecision.outcome()!=DocumentCurrentnessOutcome.ALLOW
                || !request.evidence().aclAuthorityVersion().equals(aclDecision.authorityVersion())
                || !request.evidence().permissionEvidence().permissionVersion().equals(aclDecision.permissionVersion())){
            return deny(request,aclDecision,null,aclDecision.outcome()==DocumentCurrentnessOutcome.DENY
                    ?DocumentSecurityReasonCode.ACL_DENIED:DocumentSecurityReasonCode.ACL_UNAVAILABLE);
        }
        List<DocumentEmergencyTargetRef> targets=new ArrayList<>();
        targets.add(new DocumentEmergencyTargetRef.CapabilityTarget(request.capabilityId()));
        targets.add(new DocumentEmergencyTargetRef.CorpusTarget(request.evidence().corpusKey()));
        targets.add(new DocumentEmergencyTargetRef.ProfileTarget(request.profileSafeRef()));
        if(targetBinding!=null)targets.add(new DocumentEmergencyTargetRef.IndexTarget(targetBinding.canonicalDigest()));
        request.generationProvider().ifPresent(binding -> {
            targets.add(new DocumentEmergencyTargetRef.ProviderOperationTarget(binding.operationType()));
            targets.add(new DocumentEmergencyTargetRef.ProviderBindingTarget(binding.canonicalDigest()));
        });
        DocumentEmergencyView view;
        try{view=emergency.readCurrent(List.copyOf(targets),context.absoluteDeadline());}
        catch(RuntimeException ex){return deny(request,aclDecision,null,DocumentSecurityReasonCode.EMERGENCY_UNAVAILABLE);}
        if(!bindsRequestedTargets(view, targets)||!view.allows()||!view.validUntil().isAfter(clock.instant())){
            boolean blocked=view.decisions().stream().anyMatch(d->d.outcome()==DocumentEmergencyView.Outcome.BLOCKED);
            return deny(request,aclDecision,view,bindsRequestedTargets(view, targets)&&blocked
                    ?DocumentSecurityReasonCode.EMERGENCY_BLOCKED:DocumentSecurityReasonCode.EMERGENCY_UNAVAILABLE);
        }
        return decision(request,aclDecision,view,DocumentCurrentnessOutcome.ALLOW,DocumentSecurityReasonCode.CURRENT);
    }

    private DocumentFinalCurrentnessDecision deny(FinalDocumentCurrentnessRequest request,DocumentAclCurrentnessDecision acl,
                                                   DocumentEmergencyView view,DocumentSecurityReasonCode reason){
        return decision(request,acl,view,DocumentCurrentnessOutcome.DENY,reason);
    }

    private DocumentFinalCurrentnessDecision decision(FinalDocumentCurrentnessRequest request,DocumentAclCurrentnessDecision acl,
                                                       DocumentEmergencyView view,DocumentCurrentnessOutcome outcome,DocumentSecurityReasonCode reason){
        Instant checkedAt=clock.instant();Instant validUntil=min(request.operationContext().absoluteDeadline(),checkedAt.plus(finalDecisionMaxAge));
        String aclVersion=acl==null?"unavailable":acl.decisionVersion();String emergencyVersion=view==null?"unavailable":view.viewVersion();
        String authorizationDigest=request.operationContext().resourceLimits().reference().canonicalDigest();
        String digest=DocumentFinalDecisionDigests.digest(outcome,request.evidence().invocationId(),request.operationContext().operationId(),
                request.evidence().permissionEvidence().permissionVersion(),request.candidateSetDigest(),authorizationDigest,
                request.operationContext().resourceLimits().reference().canonicalDigest(),aclVersion,emergencyVersion,checkedAt,validUntil,reason);
        return new DocumentFinalCurrentnessDecision(outcome,request.evidence().invocationId(),request.operationContext().operationId(),
                request.evidence().permissionEvidence().permissionVersion(),request.candidateSetDigest(),authorizationDigest,
                request.operationContext().resourceLimits().reference(),aclVersion,emergencyVersion,checkedAt,validUntil,digest,reason);
    }

    private static Instant min(Instant left,Instant right){return left.isBefore(right)?left:right;}

    private static boolean bindsRequestedTargets(
            DocumentEmergencyView view, List<DocumentEmergencyTargetRef> targets) {
        if (view == null || view.decisions().size() != targets.size()) return false;
        for (int index = 0; index < targets.size(); index++) {
            var expected = DocumentEmergencyGateCanonicalizer.targetBinding(targets.get(index));
            var actual = view.decisions().get(index);
            if (!expected.targetType().name().equals(actual.targetType())
                    || !expected.targetKeyDigest().equals(actual.targetDigest())) return false;
        }
        return true;
    }

    public record FinalDocumentCurrentnessRequest(
            DocumentAclExecutionEvidence evidence,
            List<SafeDocumentCandidate> candidates,
            List<String> evidenceRefs,
            ContractRef outputContract,
            String candidateSetDigest,
            String capabilityId,
            String profileSafeRef,
            java.util.Optional<com.dylan.agent.adapter.api.document.provider.DocumentProviderBindingReference> generationProvider,
            CapabilityOperationContext operationContext){
        public FinalDocumentCurrentnessRequest{Objects.requireNonNull(evidence);candidates=List.copyOf(candidates==null?List.of():candidates);
            evidenceRefs=List.copyOf(evidenceRefs==null?List.of():evidenceRefs);Objects.requireNonNull(outputContract);
            if(candidateSetDigest==null||!candidateSetDigest.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("candidateSetDigest invalid");
            new DocumentEmergencyTargetRef.CapabilityTarget(capabilityId);
            if(profileSafeRef==null||profileSafeRef.isBlank())throw new IllegalArgumentException("profileSafeRef required");
            generationProvider=generationProvider==null?java.util.Optional.empty():generationProvider;
            Objects.requireNonNull(operationContext);}
    }
}
