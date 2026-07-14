package com.dylan.esquery.document.governance.management;

import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/internal/document-governance")
public final class DocumentIndexManagementController {
    private final DocumentIndexManagementService service;private final DocumentManagementAuthorizationContextResolver authorization;
    public DocumentIndexManagementController(DocumentIndexManagementService service,DocumentManagementAuthorizationContextResolver authorization){this.service=service;this.authorization=authorization;}
    @PostMapping("/indexes/activate") public DocumentGovernanceChangeResponse activate(@RequestBody DocumentIndexActivateRequest request,Authentication authentication){return service.activate(request,authorization.resolve(authentication,DocumentManagementOperation.INDEX_ACTIVATE));}
    @PostMapping("/indexes/rollback") public DocumentGovernanceChangeResponse rollback(@RequestBody DocumentIndexRollbackRequest request,Authentication authentication){return service.rollback(request,authorization.resolve(authentication,DocumentManagementOperation.INDEX_ROLLBACK));}
    @GetMapping("/changes/{changeId}") public DocumentGovernanceChangeResponse status(@PathVariable String changeId,Authentication authentication){return service.status(changeId,authorization.resolve(authentication,DocumentManagementOperation.READ));}
    @PostMapping("/changes/{changeId}/reconcile") public DocumentGovernanceChangeResponse reconcile(@PathVariable String changeId,@RequestBody DocumentReconcileRequest request,Authentication authentication){return service.reconcile(changeId,request,authorization.resolve(authentication,DocumentManagementOperation.RECONCILE));}
}
