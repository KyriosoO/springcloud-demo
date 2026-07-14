package com.dylan.agent.adapter.api.document;
import java.util.List;
public record DocumentAllOf(List<DocumentProtectedFilterNode> children) implements DocumentProtectedFilterNode {
    public DocumentAllOf { children=List.copyOf(children); if(children.isEmpty()) throw new IllegalArgumentException("allOf children must not be empty"); }
}
