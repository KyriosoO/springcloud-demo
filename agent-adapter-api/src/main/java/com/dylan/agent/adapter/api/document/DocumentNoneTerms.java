package com.dylan.agent.adapter.api.document;
import java.util.Set;
public record DocumentNoneTerms(DocumentAclIndexField field, Set<String> values) implements DocumentProtectedFilterNode {
    public DocumentNoneTerms { values=Set.copyOf(values); if(field!=DocumentAclIndexField.DOCUMENT_ID || values.isEmpty()) throw new IllegalArgumentException("none terms only supports document ids"); }
}
