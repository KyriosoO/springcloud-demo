package com.dylan.esquery.document.governance.management;

import java.time.Instant;
import java.util.Set;

public record DocumentManagementAuthorizationContext(String serviceSubject,String actorSafeRef,
        Set<DocumentManagementScope> scopes,Instant authenticatedAt,String authenticationEvidenceDigest){
    public DocumentManagementAuthorizationContext{scopes=Set.copyOf(scopes);}
    public void require(DocumentManagementScope scope){if(!scopes.contains(scope))throw new org.springframework.security.access.AccessDeniedException("document governance scope required");}
}
