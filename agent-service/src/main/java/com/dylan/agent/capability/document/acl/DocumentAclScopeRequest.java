package com.dylan.agent.capability.document.acl;

import java.time.Instant;

/** 文档 ACL subject projection 请求。 */
public record DocumentAclScopeRequest(
        String invocationId,
        String subjectRef,
        String domain,
        String permissionEvidenceId,
        String permissionVersion,
        Instant deadline) {
}
