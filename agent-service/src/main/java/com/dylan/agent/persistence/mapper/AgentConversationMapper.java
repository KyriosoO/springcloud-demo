package com.dylan.agent.persistence.mapper;

import java.time.LocalDateTime;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import com.dylan.agent.persistence.entity.AgentConversationEntity;

/** Conversation 持久化 Mapper，负责会话的增删改查。 */
@Mapper
public interface AgentConversationMapper {

    @Insert("INSERT INTO agent_conversation (id, user_id, status, created_at, updated_at) " +
            "VALUES (#{id}, #{userId}, #{status}, #{createdAt}, #{updatedAt})")
    int insert(AgentConversationEntity entity);

    @Select("SELECT id, user_id, status, created_at, updated_at FROM agent_conversation " +
            "WHERE id = #{id} AND user_id = #{userId}")
    AgentConversationEntity selectOwned(@Param("id") String id, @Param("userId") String userId);

    @Update("UPDATE agent_conversation SET updated_at = #{updatedAt} " +
            "WHERE id = #{id} AND user_id = #{userId}")
    int touchOwned(@Param("id") String id, @Param("userId") String userId,
                    @Param("updatedAt") LocalDateTime updatedAt);

    @Update("DELETE c FROM agent_conversation c " +
            "LEFT JOIN agent_turn t ON c.id = t.conversation_id " +
            "WHERE c.updated_at < #{cutoff} AND t.id IS NULL")
    int deleteExpiredWithoutTurns(@Param("cutoff") LocalDateTime cutoff);
}
