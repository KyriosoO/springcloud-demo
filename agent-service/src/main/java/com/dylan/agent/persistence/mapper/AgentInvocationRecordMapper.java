package com.dylan.agent.persistence.mapper;

import com.dylan.agent.persistence.entity.AgentInvocationRecordEntity;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 调用生命周期权威映射器。
 */
@Mapper
public interface AgentInvocationRecordMapper {

    @Insert("INSERT INTO agent_invocation_record (" +
            "id, invocation_type, origin_type, conversation_id, turn_id, subject_type, subject_id, " +
            "owner_type, owner_id, scope_type, scope_id, agent_id, profile_version, request_correlation_id, " +
            "state, deadline_at, created_at) VALUES (" +
            "#{id}, #{invocationType}, #{originType}, #{conversationId}, #{turnId}, #{subjectType}, #{subjectId}, " +
            "#{ownerType}, #{ownerId}, #{scopeType}, #{scopeId}, #{agentId}, #{profileVersion}, " +
            "#{requestCorrelationId}, #{state}, #{deadlineAt}, #{createdAt})")
    int insert(AgentInvocationRecordEntity entity);

    @Select("SELECT id, invocation_type, origin_type, conversation_id, turn_id, subject_type, subject_id, " +
            "owner_type, owner_id, scope_type, scope_id, agent_id, profile_version, request_correlation_id, " +
            "state, response_type, checkpoint_json, checkpoint_hash, error_code, safe_message, diagnostic_id, " +
            "deadline_at, created_at, checkpointed_at, completed_at FROM agent_invocation_record WHERE id = #{id}")
    AgentInvocationRecordEntity selectById(@Param("id") String id);

    @Update("UPDATE agent_invocation_record SET checkpoint_json = #{checkpointJson}, " +
            "checkpoint_hash = #{checkpointHash}, checkpointed_at = #{checkpointedAt} " +
            "WHERE id = #{id} AND state = 'PROCESSING' AND checkpoint_hash IS NULL")
    int checkpoint(@Param("id") String id,
                   @Param("checkpointJson") String checkpointJson,
                   @Param("checkpointHash") String checkpointHash,
                   @Param("checkpointedAt") LocalDateTime checkpointedAt);

    @Update("UPDATE agent_invocation_record SET state = #{state}, response_type = #{responseType}, " +
            "error_code = #{errorCode}, safe_message = #{safeMessage}, diagnostic_id = #{diagnosticId}, " +
            "completed_at = #{completedAt} WHERE id = #{id} AND state = 'PROCESSING'")
    int finalizeTerminal(@Param("id") String id,
                         @Param("state") String state,
                         @Param("responseType") String responseType,
                         @Param("errorCode") String errorCode,
                         @Param("safeMessage") String safeMessage,
                         @Param("diagnosticId") String diagnosticId,
                         @Param("completedAt") LocalDateTime completedAt);

    @Select("SELECT id, invocation_type, origin_type, conversation_id, turn_id, subject_type, subject_id, " +
            "owner_type, owner_id, scope_type, scope_id, agent_id, profile_version, request_correlation_id, " +
            "state, response_type, checkpoint_json, checkpoint_hash, error_code, safe_message, diagnostic_id, " +
            "deadline_at, created_at, checkpointed_at, completed_at FROM agent_invocation_record " +
            "WHERE state = 'PROCESSING' AND deadline_at < #{now} ORDER BY deadline_at ASC LIMIT #{limit}")
    List<AgentInvocationRecordEntity> selectExpiredProcessing(@Param("now") LocalDateTime now,
                                                              @Param("limit") int limit);
}
