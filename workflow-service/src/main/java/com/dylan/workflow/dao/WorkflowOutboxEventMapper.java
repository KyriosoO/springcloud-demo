package com.dylan.workflow.dao;

import java.util.List;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface WorkflowOutboxEventMapper {

    @Insert("INSERT INTO workflow_outbox_event (event_id, message_json, status, attempts, last_error) "
            + "VALUES (#{eventId}, #{messageJson}, #{status}, #{attempts}, #{lastError}) "
            + "ON DUPLICATE KEY UPDATE status = VALUES(status), attempts = VALUES(attempts), "
            + "last_error = VALUES(last_error), message_json = VALUES(message_json), updated_at = NOW()")
    void upsert(WorkflowOutboxEventRow row);

    @Update("UPDATE workflow_outbox_event SET status = #{status}, attempts = #{attempts}, "
            + "last_error = #{lastError}, message_json = #{messageJson}, updated_at = NOW() "
            + "WHERE event_id = #{eventId}")
    int update(WorkflowOutboxEventRow row);

    @Select("SELECT event_id, message_json AS messageJson, status, attempts, last_error AS lastError, "
            + "created_at AS createdAt, updated_at AS updatedAt "
            + "FROM workflow_outbox_event WHERE status IN ('PENDING', 'FAILED') and attempts <= #{attempts}")
    List<WorkflowOutboxEventRow> selectRetryable(int attempts);
}
