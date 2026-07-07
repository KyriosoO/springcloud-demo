package com.dylan.agent.capability.document.acl;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;

/** Local-only document ACL scope provider for end-to-end flow testing. */
@RestController
@RequestMapping(path = "/internal/document-acl/scope", produces = MediaType.APPLICATION_JSON_VALUE)
@ConditionalOnProperty(prefix = "agent.document.acl.mock", name = "enabled", havingValue = "true")
public class MockDocumentAclScopeController {

    @PostMapping(path = "/resolve", consumes = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> resolve(@RequestBody DocumentAclScopeRequest request) {
        Instant expiresAt = Instant.now().plus(30, ChronoUnit.MINUTES);
        return Map.of(
                "subjectRef", request.subjectRef(),
                "domain", request.domain(),
                "tenantId", "tenant-local",
                "userId", "user-local",
                "departmentIds", List.of("dept-local"),
                "roleIds", List.of("role-local"),
                "attributeKeys", List.of("tax-policy-local"),
                "aclSnapshotVersion", "mock-acl-v1",
                "expiresAt", expiresAt.toString());
    }
}
