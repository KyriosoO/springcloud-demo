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
            "contract_namespace, contract_name, contract_version, record_version, protected_payload_json, " +
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
            "contract_namespace, contract_name, contract_version, record_version, protected_payload_json, " +
            "source_capability_id, source_invocation_id, source_domain, readable, expires_at, updated_at " +
            "FROM agent_context_record WHERE owner_type = #{ownerType} AND owner_id = #{ownerId} " +
            "AND scope_type = #{scopeType} AND scope_id = #{scopeId} AND context_type = #{contextType}")
    ContextRecordRow findByKey(@Param("ownerType") String ownerType,
                               @Param("ownerId") String ownerId,
                               @Param("scopeType") String scopeType,
                               @Param("scopeId") String scopeId,
                               @Param("contextType") String contextType);

    @Insert("INSERT INTO agent_context_record (" +
            "context_id, owner_type, owner_id, scope_type, scope_id, context_type, " +
            "contract_namespace, contract_name, contract_version, " +
            "record_version, protected_payload_json, source_capability_id, source_invocation_id, source_domain, " +
            "readable, expires_at, updated_at) VALUES (" +
            "#{contextId}, #{ownerType}, #{ownerId}, #{scopeType}, #{scopeId}, #{contextType}, " +
            "#{contractNamespace}, #{contractName}, #{contractVersion}, #{recordVersion}, #{protectedPayloadJson}, " +
            "#{sourceCapabilityId}, #{sourceInvocationId}, #{sourceDomain}, #{readable}, #{expiresAt}, #{updatedAt}) " +
            "")
    int insertIfAbsent(ContextRecordRow row);

    @Update("UPDATE agent_context_record SET context_id = #{row.contextId}, " +
            "contract_namespace = #{row.contractNamespace}, contract_name = #{row.contractName}, " +
            "contract_version = #{row.contractVersion}, record_version = #{row.recordVersion}, " +
            "protected_payload_json = #{row.protectedPayloadJson}, source_capability_id = #{row.sourceCapabilityId}, " +
            "source_invocation_id = #{row.sourceInvocationId}, source_domain = #{row.sourceDomain}, " +
            "readable = #{row.readable}, expires_at = #{row.expiresAt}, updated_at = #{row.updatedAt} " +
            "WHERE owner_type = #{row.ownerType} AND owner_id = #{row.ownerId} " +
            "AND scope_type = #{row.scopeType} AND scope_id = #{row.scopeId} " +
            "AND context_type = #{row.contextType} AND record_version = #{expectedCurrentVersion}")
    int updateIfVersion(@Param("row") ContextRecordRow row,
                        @Param("expectedCurrentVersion") long expectedCurrentVersion);

    @Update("UPDATE agent_context_record SET readable = 0, updated_at = #{now} " +
            "WHERE scope_type = 'CONVERSATION' AND scope_id = #{scopeId}")
    int markConversationUnreadable(@Param("scopeId") String scopeId,
                                   @Param("now") LocalDateTime now);

    @Delete("DELETE FROM agent_context_record WHERE expires_at < #{cutoff} LIMIT #{limit}")
    int deleteExpired(@Param("cutoff") LocalDateTime cutoff,
                      @Param("limit") int limit);
}
