package com.dylan.agent.capability.document.governance.emergency;

import com.dylan.agent.capability.document.governance.management.*;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.*;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Optional;

@RestController
@RequestMapping("/internal/document-governance/emergency-controls")
public final class DocumentEmergencyManagementController {
    private final DocumentEmergencyControlService service;
    private final DocumentManagementAuthorizationContextResolver authorizationResolver;
    private final DocumentApprovalEvidencePort approvals;
    private final DocumentEmergencyResolutionEvidencePort resolutionEvidence;

    public DocumentEmergencyManagementController(
            DocumentEmergencyControlService service,
            DocumentManagementAuthorizationContextResolver authorizationResolver,
            DocumentApprovalEvidencePort approvals,
            DocumentEmergencyResolutionEvidencePort resolutionEvidence) {
        this.service=service;this.authorizationResolver=authorizationResolver;
        this.approvals=approvals;this.resolutionEvidence=resolutionEvidence;
    }

    @PostMapping("/disable")
    public DocumentEmergencyChangeResponse disable(
            JwtAuthenticationToken authentication,@RequestBody DocumentEmergencyDisableRequest request){
        var authorization=authorizationResolver.resolve(authentication,DocumentManagementOperation.EMERGENCY_DISABLE);
        var target=DocumentEmergencyGateCanonicalizer.targetBinding(request.target());
        String expected=canonical("EMERGENCY-EXPECTED-1",Long.toString(request.expectedRowVersion()));
        String desired=canonical("EMERGENCY-TARGET-1","ACTIVE",target.targetKeyDigest());
        String authorizationDigest=canonical("DMA-REQUEST-1","DISABLE",request.idempotencyKey(),target.targetType().name(),
                target.targetKeyDigest(),expected,desired,request.reasonCode().name(),request.deadline().toString());
        var approval=approvals.requireApproval(new DocumentApprovalVerificationRequest(
                DocumentManagementOperation.EMERGENCY_DISABLE,target.targetKeyDigest(),expected,desired,
                Optional.empty(),authorizationDigest,request.deadline()),authorization);
        return service.disable(request,authorization,approval);
    }

    @PostMapping("/clear")
    public DocumentEmergencyChangeResponse clear(
            JwtAuthenticationToken authentication,@RequestBody DocumentEmergencyClearRequest request){
        var authorization=authorizationResolver.resolve(authentication,DocumentManagementOperation.EMERGENCY_CLEAR);
        var target=DocumentEmergencyGateCanonicalizer.targetBinding(request.target());
        String resolved=resolutionEvidence.requireCurrentEvidence(request.resolutionEvidenceId(),target,request.deadline());
        String expected=canonical("EMERGENCY-EXPECTED-1",Long.toString(request.expectedActiveRowVersion()));
        String desired=canonical("EMERGENCY-TARGET-1","CLEARED",target.targetKeyDigest());
        String authorizationDigest=canonical("DMA-REQUEST-1","CLEAR",request.idempotencyKey(),target.targetType().name(),
                target.targetKeyDigest(),expected,desired,request.resolutionEvidenceId(),resolved,request.deadline().toString());
        var approval=approvals.requireApproval(new DocumentApprovalVerificationRequest(
                DocumentManagementOperation.EMERGENCY_CLEAR,target.targetKeyDigest(),expected,desired,
                Optional.empty(),authorizationDigest,request.deadline()),authorization);
        return service.clear(request,resolved,authorization,approval);
    }

    private static String canonical(String... values){
        try{MessageDigest digest=MessageDigest.getInstance("SHA-256");for(String value:values){byte[] bytes=value.getBytes(StandardCharsets.UTF_8);digest.update(ByteBuffer.allocate(4).putInt(bytes.length).array());digest.update(bytes);}return HexFormat.of().formatHex(digest.digest());}
        catch(Exception ex){throw new IllegalStateException(ex);}
    }
}
