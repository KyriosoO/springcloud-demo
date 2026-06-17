package com.dylan.workflow.dao;

import java.util.List;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface WorkflowInstanceMapper {

    @Insert("INSERT INTO workflow_instance (process_id, domain, operation_type, business_id, submit_action, status, payload, operator, current_node_index, nodes_json) "
            + "VALUES (#{processId}, #{domain}, #{operationType}, #{businessId}, #{submitAction}, #{status}, #{payloadJson}, #{operator}, #{currentNodeIndex}, #{nodesJson})")
    void insert(WorkflowInstanceRow row);

    @Select("SELECT process_id, domain, operation_type, business_id, submit_action, status, payload AS payloadJson, "
            + "operator, current_node_index AS currentNodeIndex, nodes_json AS nodesJson, created_at AS createdAt, updated_at AS updatedAt "
            + "FROM workflow_instance WHERE process_id = #{processId}")
    WorkflowInstanceRow selectById(String processId);

    @Update("UPDATE workflow_instance SET status = #{status}, operator = #{operator}, "
            + "current_node_index = #{currentNodeIndex}, payload = #{payloadJson}, nodes_json = #{nodesJson}, "
            + "updated_at = NOW() WHERE process_id = #{processId}")
    int update(WorkflowInstanceRow row);

    @Select("SELECT process_id, domain, operation_type, business_id, submit_action, status, payload AS payloadJson, "
            + "operator, current_node_index AS currentNodeIndex, nodes_json AS nodesJson, created_at AS createdAt, updated_at AS updatedAt "
            + "FROM workflow_instance")
    List<WorkflowInstanceRow> selectAll();
}
