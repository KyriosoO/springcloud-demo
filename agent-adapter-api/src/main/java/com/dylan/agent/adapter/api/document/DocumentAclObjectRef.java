package com.dylan.agent.adapter.api.document;
public record DocumentAclObjectRef(String aclRef, String aclVersion) {
    public DocumentAclObjectRef { if(aclRef==null||aclRef.isBlank()||aclVersion==null||aclVersion.isBlank()) throw new IllegalArgumentException("ACL object ref must be complete"); }
}
