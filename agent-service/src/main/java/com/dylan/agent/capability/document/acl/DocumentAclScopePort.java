package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.document.DocumentAclScope;

/** 文档 ACL subject projection 端口。 */
public interface DocumentAclScopePort {

    DocumentAclScope resolve(DocumentAclScopeRequest request);
}
