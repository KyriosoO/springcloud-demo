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
            "state, response_type, capability_id, plan_kind, registration_identity, authorization_snapshot_ref, " +
            "context_snapshot_set_digest, metadata_version, planning_artifact_binding_digest, " +
            "checkpoint_json, checkpoint_hash, checkpoint_sequence, row_version, error_code, safe_message, diagnostic_id, " +
            "deadline_at, created_at, checkpointed_at, completed_at FROM agent_invocation_record WHERE id = #{id}")
    AgentInvocationRecordEntity selectById(@Param("id") String id);

    @Update("UPDATE agent_invocation_record SET capability_id = #{capabilityId}, plan_kind = #{planKind}, " +
            "registration_identity = #{registrationIdentity}, authorization_snapshot_ref = #{authorizationSnapshotRef}, " +
            "context_snapshot_set_digest = #{contextSnapshotSetDigest}, metadata_version = #{metadataVersion}, " +
            "planning_artifact_binding_digest = #{planningArtifactBindingDigest}, checkpoint_json = #{checkpointJson}, " +
            "checkpoint_hash = #{checkpointHash}, checkpoint_sequence = 1, checkpointed_at = #{checkpointedAt}, " +
            "row_version = row_version + 1 WHERE id = #{id} AND state = 'PROCESSING' " +
            "AND checkpoint_sequence = #{expectedCheckpointSequence} AND row_version = #{expectedRowVersion}")
    int checkpoint(@Param("id") String id,
                   @Param("capabilityId") String capabilityId,
                   @Param("planKind") String planKind,
                   @Param("registrationIdentity") String registrationIdentity,
                   @Param("authorizationSnapshotRef") String authorizationSnapshotRef,
                   @Param("contextSnapshotSetDigest") String contextSnapshotSetDigest,
                   @Param("metadataVersion") String metadataVersion,
                   @Param("planningArtifactBindingDigest") String planningArtifactBindingDigest,
                   @Param("checkpointJson") String checkpointJson,
                   @Param("checkpointHash") String checkpointHash,
                   @Param("checkpointedAt") LocalDateTime checkpointedAt,
                   @Param("expectedCheckpointSequence") long expectedCheckpointSequence,
                   @Param("expectedRowVersion") long expectedRowVersion);

    @Update("UPDATE agent_invocation_record SET state = #{state}, response_type = #{responseType}, " +
            "error_code = #{errorCode}, safe_message = #{safeMessage}, diagnostic_id = #{diagnosticId}, " +
            "completed_at = #{completedAt}, row_version = row_version + 1 " +
            "WHERE id = #{id} AND state = 'PROCESSING' AND row_version = #{expectedRowVersion}")
    int finalizeTerminal(@Param("id") String id,
                         @Param("state") String state,
                         @Param("responseType") String responseType,
                         @Param("errorCode") String errorCode,
                         @Param("safeMessage") String safeMessage,
                         @Param("diagnosticId") String diagnosticId,
                         @Param("completedAt") LocalDateTime completedAt,
                         @Param("expectedRowVersion") long expectedRowVersion);

    @Select("SELECT id, invocation_type, origin_type, conversation_id, turn_id, subject_type, subject_id, " +
            "owner_type, owner_id, scope_type, scope_id, agent_id, profile_version, request_correlation_id, " +
            "state, response_type, capability_id, plan_kind, registration_identity, authorization_snapshot_ref, " +
            "context_snapshot_set_digest, metadata_version, planning_artifact_binding_digest, " +
            "checkpoint_json, checkpoint_hash, checkpoint_sequence, row_version, error_code, safe_message, diagnostic_id, " +
            "deadline_at, created_at, checkpointed_at, completed_at FROM agent_invocation_record " +
            "WHERE state = 'PROCESSING' AND deadline_at < #{now} ORDER BY deadline_at ASC LIMIT #{limit}")
    List<AgentInvocationRecordEntity> selectExpiredProcessing(@Param("now") LocalDateTime now,
                                                              @Param("limit") int limit);
}
