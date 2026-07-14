package com.dylan.agent.capability.document.governance.provider;

import com.dylan.agent.capability.document.governance.management.*;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/internal/document-governance/providers")
public final class DocumentProviderManagementController {
    private final DocumentProviderManagementService service;
    private final DocumentManagementAuthorizationContextResolver authorization;
    public DocumentProviderManagementController(DocumentProviderManagementService service,
            DocumentManagementAuthorizationContextResolver authorization){this.service=service;this.authorization=authorization;}
    @PostMapping("/activate") public DocumentGovernanceChangeResponse activate(JwtAuthenticationToken authentication,@RequestBody DocumentProviderActivateRequest request){return service.activate(request,authorization.resolve(authentication,DocumentManagementOperation.PROVIDER_ACTIVATE));}
    @PostMapping("/deactivate") public DocumentGovernanceChangeResponse deactivate(JwtAuthenticationToken authentication,@RequestBody DocumentProviderDeactivateRequest request){return service.deactivate(request,authorization.resolve(authentication,DocumentManagementOperation.PROVIDER_DEACTIVATE));}
    @PostMapping("/rollback") public DocumentGovernanceChangeResponse rollback(JwtAuthenticationToken authentication,@RequestBody DocumentProviderRollbackRequest request){return service.rollback(request,authorization.resolve(authentication,DocumentManagementOperation.PROVIDER_ROLLBACK));}
}
