package com.dylan.agent.metadata.context.internal;

import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.time.LocalDateTime;

/**
 * 已持久化 Capability Context 记录的映射器。
 */
@Mapper
public interface ContextRecordMapper {

    @Select("SELECT context_id, owner_type, owner_id, scope_type, scope_id, context_type, " +
            "contract_schema, contract_version, record_version, protected_payload_json, " +
            "source_capability_id, source_invocation_id, source_domain, readable, expires_at, updated_at " +
            "FROM agent_context_record WHERE owner_type = #{ownerType} AND owner_id = #{ownerId} " +
            "AND scope_type = #{scopeType} AND scope_id = #{scopeId} AND context_type = #{contextType} " +
            "AND readable = 1 AND expires_at > #{now}")
    ContextRecordRow findCurrent(@Param("ownerType") String ownerType,
                                 @Param("ownerId") String ownerId,
                                 @Param("scopeType") String scopeType,
                                 @Param("scopeId") String scopeId,
                                 @Param("contextType") String contextType,
                                 @Param("now") LocalDateTime now);

    @Select("SELECT context_id, owner_type, owner_id, scope_type, scope_id, context_type, " +
            "contract_schema, contract_version, record_version, protected_payload_json, " +
            "source_capability_id, source_invocation_id, source_domain, readable, expires_at, updated_at " +
            "FROM agent_context_record WHERE owner_type = #{ownerType} AND owner_id = #{ownerId} " +
            "AND scope_type = #{scopeType} AND scope_id = #{scopeId} AND context_type = #{contextType}")
    ContextRecordRow findByKey(@Param("ownerType") String ownerType,
                               @Param("ownerId") String ownerId,
                               @Param("scopeType") String scopeType,
                               @Param("scopeId") String scopeId,
                               @Param("contextType") String contextType);

    @Insert("INSERT INTO agent_context_record (" +
            "context_id, owner_type, owner_id, scope_type, scope_id, context_type, contract_schema, contract_version, " +
            "record_version, protected_payload_json, source_capability_id, source_invocation_id, source_domain, " +
            "readable, expires_at, updated_at) VALUES (" +
            "#{contextId}, #{ownerType}, #{ownerId}, #{scopeType}, #{scopeId}, #{contextType}, " +
            "#{contractSchema}, #{contractVersion}, #{recordVersion}, #{protectedPayloadJson}, " +
            "#{sourceCapabilityId}, #{sourceInvocationId}, #{sourceDomain}, #{readable}, #{expiresAt}, #{updatedAt}) " +
            "ON DUPLICATE KEY UPDATE context_id = VALUES(context_id), contract_schema = VALUES(contract_schema), " +
            "contract_version = VALUES(contract_version), record_version = VALUES(record_version), " +
            "protected_payload_json = VALUES(protected_payload_json), source_capability_id = VALUES(source_capability_id), " +
            "source_invocation_id = VALUES(source_invocation_id), source_domain = VALUES(source_domain), " +
            "readable = VALUES(readable), expires_at = VALUES(expires_at), updated_at = VALUES(updated_at)")
    int upsert(ContextRecordRow row);

    @Update("UPDATE agent_context_record SET readable = 0, updated_at = #{now} " +
            "WHERE scope_type = 'CONVERSATION' AND scope_id = #{scopeId}")
    int markConversationUnreadable(@Param("scopeId") String scopeId,
                                   @Param("now") LocalDateTime now);

    @Delete("DELETE FROM agent_context_record WHERE expires_at < #{cutoff} LIMIT #{limit}")
    int deleteExpired(@Param("cutoff") LocalDateTime cutoff,
                      @Param("limit") int limit);
}
