package com.dylan.agent.capability.document.governance.emergency;

import com.dylan.agent.capability.document.governance.management.DocumentManagementAuthorizationContextResolver;
import com.dylan.agent.capability.document.governance.management.DocumentManagementOperation;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/internal/document-governance/emergency-gate-evidence")
public final class DocumentEmergencyGateEvidenceController {
    private final DocumentEmergencyGateEvidenceIssuer issuer;
    private final DocumentManagementAuthorizationContextResolver authorization;

    public DocumentEmergencyGateEvidenceController(
            DocumentEmergencyGateEvidenceIssuer issuer,
            DocumentManagementAuthorizationContextResolver authorization) {
        this.issuer = issuer;
        this.authorization = authorization;
    }

    @PostMapping
    public DocumentEmergencyGateEvidence issue(
            JwtAuthenticationToken authentication,
            @RequestBody DocumentEmergencyGateEvidenceIssueRequest request) {
        return issuer.issueForRollout(request, authorization.resolve(
                authentication, DocumentManagementOperation.EMERGENCY_EVIDENCE_ISSUE));
    }
}
