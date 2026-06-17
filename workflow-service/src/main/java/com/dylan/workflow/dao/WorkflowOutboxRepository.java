package com.dylan.workflow.dao;

import java.util.ArrayList;
import java.util.List;

import org.springframework.stereotype.Repository;

import com.dylan.workflow.model.WorkflowOutboxEvent;
import com.dylan.workflow.model.WorkflowOutboxStatus;
import com.dylan.workflow.web.WorkflowActionMessage;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * 数据库版 Outbox 仓库。
 */
@Repository
public class WorkflowOutboxRepository {

    private final WorkflowOutboxEventMapper mapper;
    private final ObjectMapper objectMapper;

    public WorkflowOutboxRepository(WorkflowOutboxEventMapper mapper, ObjectMapper objectMapper) {
        this.mapper = mapper;
        this.objectMapper = objectMapper;
    }

    public void save(WorkflowOutboxEvent event) {
        mapper.upsert(toRow(event));
    }

    public List<WorkflowOutboxEvent> findRetryable() {
    	int attempts = 10;
        List<WorkflowOutboxEventRow> rows = mapper.selectRetryable(attempts);
        List<WorkflowOutboxEvent> events = new ArrayList<>();
        for (WorkflowOutboxEventRow row : rows) {
            events.add(fromRow(row));
        }
        return events;
    }

    private WorkflowOutboxEventRow toRow(WorkflowOutboxEvent event) {
        WorkflowOutboxEventRow row = new WorkflowOutboxEventRow();
        row.setEventId(event.getEventId());
        row.setMessageJson(toJson(event.getMessage()));
        row.setStatus(event.getStatus().name());
        row.setAttempts(event.getAttempts());
        row.setLastError(event.getLastError());
        return row;
    }

    private WorkflowOutboxEvent fromRow(WorkflowOutboxEventRow row) {
        WorkflowOutboxEvent event = new WorkflowOutboxEvent();
        event.setEventId(row.getEventId());
        event.setMessage(fromJson(row.getMessageJson(), WorkflowActionMessage.class));
        event.setStatus(WorkflowOutboxStatus.valueOf(row.getStatus()));
        event.setAttempts(row.getAttempts());
        event.setLastError(row.getLastError());
        return event;
    }

    private String toJson(Object obj) {
        if (obj == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(obj);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to serialize to JSON", e);
        }
    }

    private <T> T fromJson(String json, Class<T> clazz) {
        if (json == null) {
            return null;
        }
        try {
            return objectMapper.readValue(json, clazz);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to deserialize from JSON", e);
        }
    }
}
