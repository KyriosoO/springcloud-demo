package com.dylan.employee.dao;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Repository;

import com.dylan.employee.model.EmployeeWorkflowInboxMessage;
import com.dylan.employee.model.EmployeeWorkflowInboxStatus;
import com.dylan.workflow.web.WorkflowActionMessage;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * 数据库版 Inbox 仓库，用于工作流事件幂等处理。
 * <p>
 * 通过乐观锁（UPDATE ... WHERE status = expectedStatus）保证
 * 多线程/多实例环境下的幂等消费安全。
 */
@Repository
public class EmployeeWorkflowInboxRepository {

    private static final Logger log = LoggerFactory.getLogger(EmployeeWorkflowInboxRepository.class);

    private final EmployeeWorkflowInboxMessageMapper mapper;
    private final ObjectMapper objectMapper;

    public EmployeeWorkflowInboxRepository(EmployeeWorkflowInboxMessageMapper mapper, ObjectMapper objectMapper) {
        this.mapper = mapper;
        this.objectMapper = objectMapper;
    }

    public void saveIfAbsent(WorkflowActionMessage message) {
        String eventId = eventIdOf(message);
        EmployeeWorkflowInboxMessageRow row = new EmployeeWorkflowInboxMessageRow();
        row.setEventId(eventId);
        row.setMessageJson(toJson(message));
        row.setStatus(EmployeeWorkflowInboxStatus.RECEIVED.name());
        int inserted = mapper.insertIfAbsent(row);
        if (inserted > 0) {
            log.debug("Inbox message inserted, eventId={}", eventId);
        }
    }

    public List<EmployeeWorkflowInboxMessage> findRetryable() {
    	LocalDateTime ldt = LocalDateTime.now().minusDays(1);
        List<EmployeeWorkflowInboxMessageRow> rows = mapper.selectRetryable(ldt);
        List<EmployeeWorkflowInboxMessage> messages = new ArrayList<>();
        for (EmployeeWorkflowInboxMessageRow row : rows) {
            EmployeeWorkflowInboxMessage msg = new EmployeeWorkflowInboxMessage();
            msg.setEventId(row.getEventId());
            msg.setMessage(fromJson(row.getMessageJson(), WorkflowActionMessage.class));
            msg.setStatus(EmployeeWorkflowInboxStatus.valueOf(row.getStatus()));
            msg.setLastError(row.getLastError());
            messages.add(msg);
        }
        return messages;
    }

    public boolean markProcessing(String eventId) {
        int updated = mapper.updateStatusByExpected(eventId,
                EmployeeWorkflowInboxStatus.PROCESSING.name(), null,
                EmployeeWorkflowInboxStatus.RECEIVED.name());
        if (updated == 0) {
            // 也尝试从 FAILED 状态转为 PROCESSING（重试场景）
            updated = mapper.updateStatusByExpected(eventId,
                    EmployeeWorkflowInboxStatus.PROCESSING.name(), null,
                    EmployeeWorkflowInboxStatus.FAILED.name());
        }
        return updated > 0;
    }

    public void markProcessed(String eventId) {
        mapper.updateStatusByExpected(eventId,
                EmployeeWorkflowInboxStatus.PROCESSED.name(), null,
                EmployeeWorkflowInboxStatus.PROCESSING.name());
    }

    public void markFailed(String eventId, Exception e) {
        String error = e.getMessage();
        if (error != null && error.length() > 1024) {
            error = error.substring(0, 1024);
        }
        mapper.updateStatusByExpected(eventId,
                EmployeeWorkflowInboxStatus.FAILED.name(), error,
                EmployeeWorkflowInboxStatus.PROCESSING.name());
    }

    private String eventIdOf(WorkflowActionMessage message) {
        if (message.getEventId() != null && !message.getEventId().isBlank()) {
            return message.getEventId();
        }
        return message.getProcessId() + ":" + message.getActionName() + ":" + message.getActionType();
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
