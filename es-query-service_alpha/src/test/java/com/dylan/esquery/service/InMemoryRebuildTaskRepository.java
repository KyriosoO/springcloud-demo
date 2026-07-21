package com.dylan.esquery.service;

import com.dylan.esquery.api.model.RebuildTask;

import java.time.Instant;
import java.util.Collection;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

class InMemoryRebuildTaskRepository implements RebuildTaskRepository {
    private final Map<String, RebuildTask> tasks = new ConcurrentHashMap<>();

    @Override
    public RebuildTask create(String taskId, String index, String targetIndex, String type) {
        RebuildTask task = new RebuildTask();
        task.setTaskId(taskId);
        task.setIndex(index);
        task.setTargetIndex(targetIndex);
        task.setType(type);
        task.setStatus("PENDING");
        task.setCreatedAt(Instant.now());
        task.setUpdatedAt(task.getCreatedAt());
        tasks.put(taskId, task);
        return task;
    }

    @Override
    public RebuildTask findById(String taskId) {
        RebuildTask task = tasks.get(taskId);
        if (task == null) {
            throw new IllegalArgumentException("Rebuild task not found: " + taskId);
        }
        return task;
    }

    @Override
    public Collection<RebuildTask> findAll() {
        return tasks.values();
    }

    @Override
    public void markRunning(String taskId) {
        RebuildTask task = findById(taskId);
        task.setStatus("RUNNING");
        task.setUpdatedAt(Instant.now());
    }

    @Override
    public void markProgress(String taskId, long totalIndexed, String lastCursor) {
        RebuildTask task = findById(taskId);
        task.setTotalIndexed(totalIndexed);
        task.setLastCursor(lastCursor);
        task.setUpdatedAt(Instant.now());
    }

    @Override
    public void markSuccess(String taskId) {
        RebuildTask task = findById(taskId);
        task.setStatus("SUCCESS");
        task.setUpdatedAt(Instant.now());
    }

    @Override
    public void markValidationPassed(String taskId, String digest, String message) {
        RebuildTask task = findById(taskId);
        Instant now = Instant.now();
        task.setValidationStatus("PASSED");
        task.setValidationDigest(digest);
        task.setValidatedAt(now);
        task.setValidationMessage(message);
        task.setUpdatedAt(now);
    }

    @Override
    public void markValidationSkipped(String taskId, String message) {
        RebuildTask task = findById(taskId);
        Instant now = Instant.now();
        task.setValidationStatus("SKIPPED");
        task.setValidationDigest(null);
        task.setValidatedAt(now);
        task.setValidationMessage(message);
        task.setUpdatedAt(now);
    }

    @Override
    public void markValidationFailed(String taskId, String message) {
        RebuildTask task = findById(taskId);
        Instant now = Instant.now();
        task.setValidationStatus("FAILED");
        task.setValidationDigest(null);
        task.setValidatedAt(now);
        task.setValidationMessage(message);
        task.setUpdatedAt(now);
    }

    @Override
    public void markFailed(String taskId, Exception e) {
        RebuildTask task = findById(taskId);
        task.setStatus("FAILED");
        task.setErrorMessage(e.getMessage());
        task.setValidationStatus("FAILED");
        task.setValidationDigest(null);
        task.setValidatedAt(Instant.now());
        task.setValidationMessage(e.getMessage());
        task.setUpdatedAt(Instant.now());
    }
}
