package com.dylan.agent.persistence.mapper;

import java.time.LocalDateTime;
import java.util.List;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import com.dylan.agent.persistence.entity.AgentTurnEntity;

/** 轮次持久化映射器，D03 后终态只允许由生命周期终结方法写入。 */
@Mapper
public interface AgentTurnMapper {

    @Insert("INSERT INTO agent_turn (id, conversation_id, invocation_id, user_id, user_message, status, created_at) " +
            "VALUES (#{id}, #{conversationId}, #{invocationId}, #{userId}, #{userMessage}, #{status}, #{createdAt})")
    int insert(AgentTurnEntity entity);

    @Select("SELECT id, conversation_id, invocation_id, user_id, user_message, response_type, " +
            "assistant_message, status, error_code, created_at, completed_at " +
            "FROM agent_turn " +
            "WHERE conversation_id = #{conversationId} AND user_id = #{userId} AND status = 'SUCCEEDED' " +
            "AND (invocation_id IS NULL OR invocation_id <> #{currentInvocationId}) " +
            "ORDER BY turn_seq DESC LIMIT #{limit}")
    List<AgentTurnEntity> selectRecentSucceededBeforeInvocation(
            @Param("conversationId") String conversationId,
            @Param("userId") String userId,
            @Param("currentInvocationId") String currentInvocationId,
            @Param("limit") int limit);

    @Update("UPDATE agent_turn SET response_type = #{responseType}, assistant_message = #{assistantMessage}, " +
            "status = 'SUCCEEDED', completed_at = #{completedAt} " +
            "WHERE id = #{id} AND invocation_id = #{invocationId} AND status = 'PROCESSING'")
    int finalizeSuccess(@Param("id") String id,
                        @Param("invocationId") String invocationId,
                        @Param("responseType") String responseType,
                        @Param("assistantMessage") String assistantMessage,
                        @Param("completedAt") LocalDateTime completedAt);

    @Update("UPDATE agent_turn SET error_code = #{errorCode}, assistant_message = #{assistantMessage}, " +
            "status = 'FAILED', completed_at = #{completedAt} " +
            "WHERE id = #{id} AND invocation_id = #{invocationId} AND status = 'PROCESSING'")
    int finalizeFailure(@Param("id") String id,
                        @Param("invocationId") String invocationId,
                        @Param("errorCode") String errorCode,
                        @Param("assistantMessage") String assistantMessage,
                        @Param("completedAt") LocalDateTime completedAt);

    @Update("DELETE FROM agent_turn WHERE created_at < #{cutoff}")
    int deleteBefore(@Param("cutoff") LocalDateTime cutoff);
}
