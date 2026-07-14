package com.dylan.agent.capability.document.governance.provider;

import com.dylan.agent.capability.document.governance.management.*;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/internal/document-governance/changes")
public final class DocumentGovernanceChangeController {
    private final DocumentProviderManagementService service;private final DocumentManagementAuthorizationContextResolver authorization;
    public DocumentGovernanceChangeController(DocumentProviderManagementService service,DocumentManagementAuthorizationContextResolver authorization){this.service=service;this.authorization=authorization;}
    @GetMapping("/{changeId}") public DocumentGovernanceChangeResponse status(JwtAuthenticationToken authentication,@PathVariable String changeId){return service.status(changeId,authorization.resolve(authentication,DocumentManagementOperation.GOVERNANCE_READ));}
    @PostMapping("/{changeId}/reconcile") public DocumentGovernanceChangeResponse reconcile(JwtAuthenticationToken authentication,@PathVariable String changeId,@RequestBody DocumentReconcileRequest request){return service.reconcile(changeId,request,authorization.resolve(authentication,DocumentManagementOperation.GOVERNANCE_RECONCILE));}
}
