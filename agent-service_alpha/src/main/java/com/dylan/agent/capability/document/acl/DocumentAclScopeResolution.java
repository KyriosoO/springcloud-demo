package com.dylan.agent.capability.document.acl;

/** ACL authority 的封闭结果；调用失败不得伪装为空 scope。 */
public sealed interface DocumentAclScopeResolution
        permits DocumentAclScopeAllowed, DocumentAclScopeDenied, DocumentAclScopeFailed {
}
