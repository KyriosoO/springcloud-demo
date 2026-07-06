package com.dylan.agent.capability.document;

import com.dylan.agent.capability.document.acl.DisabledDocumentAclScopePort;
import com.dylan.agent.capability.document.acl.DocumentAclScopeRequest;
import com.dylan.agent.capability.document.acl.HttpDocumentAclScopeClient;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestClient;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentAclScopePortTest {

    @Test
    void disabledPortFailsClosed() {
        DisabledDocumentAclScopePort port = new DisabledDocumentAclScopePort();

        assertThatThrownBy(() -> port.resolve(new DocumentAclScopeRequest(
                "inv-1",
                "user:u-1",
                "policy_document",
                "perm-evidence",
                "perm-v1",
                Instant.now().plusSeconds(30))))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("disabled");
    }

    @Test
    void httpClientFailsClosedWhenPermissionEvidenceIsMissing() {
        HttpDocumentAclScopeClient client = new HttpDocumentAclScopeClient(RestClient.builder().build());

        assertThatThrownBy(() -> client.resolve(new DocumentAclScopeRequest(
                "inv-1",
                "user:u-1",
                "policy_document",
                null,
                "perm-v1",
                Instant.now().plusSeconds(30))))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("permissionEvidenceId");
    }
}
