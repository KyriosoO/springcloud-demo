package com.dylan.agent.persistence.mapper;

import java.time.LocalDateTime;
import java.util.List;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import com.dylan.agent.persistence.entity.AgentTurnEntity;

/** Turn 持久化 Mapper，负责对话轮次的增删改查。completeSuccess/completeFailure 使用 CAS 乐观锁（WHERE status = 'PROCESSING'）。 */
@Mapper
public interface AgentTurnMapper {

    @Insert("INSERT INTO agent_turn (id, conversation_id, user_id, user_message, status, created_at) " +
            "VALUES (#{id}, #{conversationId}, #{userId}, #{userMessage}, #{status}, #{createdAt})")
    int insert(AgentTurnEntity entity);

    @Select("SELECT id, conversation_id, user_id, user_message, intent, response_type, " +
            "assistant_message, query_context_json, status, error_code, created_at, completed_at " +
            "FROM agent_turn " +
            "WHERE conversation_id = #{conversationId} AND user_id = #{userId} AND status = 'SUCCEEDED' " +
            "ORDER BY turn_seq DESC LIMIT #{limit}")
    List<AgentTurnEntity> selectRecentSucceeded(@Param("conversationId") String conversationId,
                                                 @Param("userId") String userId,
                                                 @Param("limit") int limit);

    @Select("SELECT id, conversation_id, user_id, user_message, intent, response_type, " +
            "assistant_message, query_context_json, status, error_code, created_at, completed_at " +
            "FROM agent_turn " +
            "WHERE conversation_id = #{conversationId} AND user_id = #{userId} " +
            "AND status = 'SUCCEEDED' AND intent = 'QUERY' AND query_context_json IS NOT NULL " +
            "ORDER BY turn_seq DESC LIMIT 1")
    AgentTurnEntity selectLatestSucceededQuery(@Param("conversationId") String conversationId,
                                                @Param("userId") String userId);

    @Update("UPDATE agent_turn SET intent = #{intent}, response_type = #{responseType}, " +
            "assistant_message = #{assistantMessage}, query_context_json = #{contextJson}, " +
            "status = 'SUCCEEDED', completed_at = #{completedAt} " +
            "WHERE id = #{id} AND status = 'PROCESSING'")
    int completeSuccess(@Param("id") String id,
                        @Param("intent") String intent,
                        @Param("responseType") String responseType,
                        @Param("assistantMessage") String assistantMessage,
                        @Param("contextJson") String contextJson,
                        @Param("completedAt") LocalDateTime completedAt);

    @Update("UPDATE agent_turn SET error_code = #{errorCode}, " +
            "assistant_message = #{assistantMessage}, status = 'FAILED', completed_at = #{completedAt} " +
            "WHERE id = #{id} AND status = 'PROCESSING'")
    int completeFailure(@Param("id") String id,
                        @Param("errorCode") String errorCode,
                        @Param("assistantMessage") String assistantMessage,
                        @Param("completedAt") LocalDateTime completedAt);

    @Update("DELETE FROM agent_turn WHERE created_at < #{cutoff}")
    int deleteBefore(@Param("cutoff") LocalDateTime cutoff);
}
