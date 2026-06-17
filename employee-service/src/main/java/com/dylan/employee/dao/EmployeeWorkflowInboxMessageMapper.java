package com.dylan.employee.dao;

import java.time.LocalDateTime;
import java.util.List;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface EmployeeWorkflowInboxMessageMapper {

    @Insert("INSERT IGNORE INTO employee_workflow_inbox_message (event_id, message_json, status, last_error) "
            + "VALUES (#{eventId}, #{messageJson}, #{status}, #{lastError})")
    int insertIfAbsent(EmployeeWorkflowInboxMessageRow row);

    @Select("SELECT event_id, message_json AS messageJson, status, last_error AS lastError, "
            + "created_at AS createdAt, updated_at AS updatedAt "
            + "FROM employee_workflow_inbox_message WHERE status IN ('RECEIVED', 'FAILED') and created_at <= #{createdAt}")
    List<EmployeeWorkflowInboxMessageRow> selectRetryable(@Param("createdAt") LocalDateTime createdAt);

    @Update("UPDATE employee_workflow_inbox_message SET status = #{newStatus}, "
            + "last_error = #{lastError}, updated_at = NOW() "
            + "WHERE event_id = #{eventId} AND status = #{expectedStatus}")
    int updateStatusByExpected(@Param("eventId") String eventId,
                               @Param("newStatus") String newStatus,
                               @Param("lastError") String lastError,
                               @Param("expectedStatus") String expectedStatus);
}
