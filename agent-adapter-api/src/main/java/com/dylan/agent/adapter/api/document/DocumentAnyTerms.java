package com.dylan.agent.adapter.api.document;
import java.util.Set;
public record DocumentAnyTerms(DocumentAclIndexField field, Set<String> values) implements DocumentProtectedFilterNode {
    public DocumentAnyTerms { values=Set.copyOf(values); if(values.isEmpty()) throw new IllegalArgumentException("any terms must not be empty"); if(field==DocumentAclIndexField.TENANT_ID || field==DocumentAclIndexField.STATUS || field==DocumentAclIndexField.VISIBILITY) throw new IllegalArgumentException("field does not support any terms"); }
}
