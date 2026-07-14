package com.dylan.agent.capability.document.acl;

/** 文档对象访问范围的 capability-local current authority 端口。 */
public interface DocumentAclScopePort {

    DocumentAclScopeResolution resolve(DocumentAclScopeRequest request);
}
