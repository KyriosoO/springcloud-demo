package com.dylan.agent.persistence.mapper;

import com.dylan.agent.persistence.entity.AgentInvocationResultEntity;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * 过滤后调用结果的映射器。
 */
@Mapper
public interface AgentInvocationResultMapper {

    @Insert("INSERT INTO agent_invocation_result (" +
            "id, invocation_id, output_contract_schema, output_contract_version, payload_json, " +
            "safe_message, safe_summary, created_at) VALUES (" +
            "#{id}, #{invocationId}, #{outputContractSchema}, #{outputContractVersion}, #{payloadJson}, " +
            "#{safeMessage}, #{safeSummary}, #{createdAt})")
    int insert(AgentInvocationResultEntity entity);

    @Select("SELECT id, invocation_id, output_contract_schema, output_contract_version, payload_json, " +
            "safe_message, safe_summary, created_at FROM agent_invocation_result " +
            "WHERE invocation_id = #{invocationId}")
    AgentInvocationResultEntity selectByInvocationId(@Param("invocationId") String invocationId);
}
