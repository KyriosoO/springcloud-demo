package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.document.DocumentAclScope;

/** 未配置 ACL scope 服务时 fail closed。 */
public final class DisabledDocumentAclScopePort implements DocumentAclScopePort {

    @Override
    public DocumentAclScope resolve(DocumentAclScopeRequest request) {
        throw new IllegalStateException("document ACL scope resolver is disabled");
    }
}
