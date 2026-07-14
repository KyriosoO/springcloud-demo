package com.dylan.agent.adapter.api.document;
import java.util.List;
public record DocumentAnyOf(List<DocumentProtectedFilterNode> children) implements DocumentProtectedFilterNode {
    public DocumentAnyOf { children=List.copyOf(children); if(children.isEmpty()) throw new IllegalArgumentException("anyOf children must not be empty"); }
}
