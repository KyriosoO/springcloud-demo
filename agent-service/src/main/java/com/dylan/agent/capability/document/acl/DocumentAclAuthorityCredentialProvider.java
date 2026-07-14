package com.dylan.agent.capability.document.acl;

import com.dylan.common.security.ServiceTokenProvider;

import java.util.Objects;

/** ACL authority 专用凭据边界，不复用 Document Provider header provider。 */
public final class DocumentAclAuthorityCredentialProvider {
    private final ServiceTokenProvider serviceTokenProvider;

    public DocumentAclAuthorityCredentialProvider(ServiceTokenProvider serviceTokenProvider) {
        this.serviceTokenProvider = Objects.requireNonNull(serviceTokenProvider);
    }

    public String authorizationHeader() {
        String token = serviceTokenProvider.token();
        if (token == null || token.isBlank()) {
            throw new IllegalStateException("document ACL authority credential is unavailable");
        }
        return "Bearer " + token.trim();
    }
}
