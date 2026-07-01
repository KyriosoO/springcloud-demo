package com.dylan.agent.invocation.model;

import java.util.Objects;

/**
 * TaskInvocationOrigin: D06 TASK 来源（runId + taskId + attemptId）。
 * D03 不创建此实例。D06 Coordinator 负责构建。
 */
public final class TaskInvocationOrigin implements InvocationOrigin {

    private final String runId;
    private final String taskId;
    private final String attemptId;

    public TaskInvocationOrigin(String runId, String taskId, String attemptId) {
        this.runId = Objects.requireNonNull(runId);
        this.taskId = Objects.requireNonNull(taskId);
        this.attemptId = Objects.requireNonNull(attemptId);
        if (runId.isBlank()) {
            throw new IllegalArgumentException("runId must not be blank");
        }
        if (taskId.isBlank()) {
            throw new IllegalArgumentException("taskId must not be blank");
        }
        if (attemptId.isBlank()) {
            throw new IllegalArgumentException("attemptId must not be blank");
        }
    }

    @Override
    public boolean isCompatibleWith(InvocationType type) {
        return type == InvocationType.TASK;
    }

    public String runId() { return runId; }
    public String taskId() { return taskId; }
    public String attemptId() { return attemptId; }
}
