package com.dylan.esquery.document;

import java.util.UUID;

/** 仅由 task lease 派生的内部写 handle；不暴露 public builder/DTO。 */
public final class IndexBuildTargetHandle {
    private final String taskId;
    private final String physicalIndex;
    private final String nonce;

    IndexBuildTargetHandle(String taskId, String physicalIndex) {
        if (taskId == null || taskId.isBlank() || physicalIndex == null || !physicalIndex.startsWith("agent-doc-")) {
            throw new IllegalArgumentException("document index build target invalid");
        }
        this.taskId = taskId;
        this.physicalIndex = physicalIndex;
        this.nonce = UUID.randomUUID().toString();
    }

    public String taskId() { return taskId; }
    public String physicalIndex() { return physicalIndex; }
    String nonce() { return nonce; }
    @Override public String toString() { return "IndexBuildTargetHandle[redacted]"; }
}
