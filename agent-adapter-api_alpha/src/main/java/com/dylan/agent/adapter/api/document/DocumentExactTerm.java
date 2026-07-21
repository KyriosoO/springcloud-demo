package com.dylan.agent.adapter.api.document;
public record DocumentExactTerm(DocumentAclIndexField field, String value) implements DocumentProtectedFilterNode {
    public DocumentExactTerm { if(field==null || value==null || value.isBlank()) throw new IllegalArgumentException("exact term must be complete"); if(field!=DocumentAclIndexField.TENANT_ID && field!=DocumentAclIndexField.STATUS && field!=DocumentAclIndexField.VISIBILITY) throw new IllegalArgumentException("field does not support exact term"); }
}
