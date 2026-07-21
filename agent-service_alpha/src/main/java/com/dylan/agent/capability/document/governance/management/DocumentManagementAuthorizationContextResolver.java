package com.dylan.agent.capability.document.governance.management;

import org.springframework.security.core.Authentication;

public interface DocumentManagementAuthorizationContextResolver {
    DocumentManagementAuthorizationContext resolve(
            Authentication authentication, DocumentManagementOperation operation);
}
