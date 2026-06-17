package com.dylan.workflow.dao;

import java.util.ArrayList;
import java.util.List;
import java.util.NoSuchElementException;

import org.springframework.stereotype.Repository;

import com.dylan.workflow.model.WorkflowInstance;
import com.dylan.workflow.model.WorkflowNodeInstance;
import com.dylan.workflow.model.WorkflowStatus;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

@Repository
public class WorkflowInstanceRepository {

    private final WorkflowInstanceMapper mapper;
    private final ObjectMapper objectMapper;

    public WorkflowInstanceRepository(WorkflowInstanceMapper mapper, ObjectMapper objectMapper) {
        this.mapper = mapper;
        this.objectMapper = objectMapper;
    }

    public void save(WorkflowInstance instance) {
        mapper.insert(toRow(instance));
    }

    public WorkflowInstance findById(String processId) {
        WorkflowInstanceRow row = mapper.selectById(processId);
        if (row == null) {
            throw new NoSuchElementException("Workflow instance not found: " + processId);
        }
        return fromRow(row);
    }

    public void update(WorkflowInstance instance) {
        mapper.update(toRow(instance));
    }

    public List<WorkflowInstance> findAll() {
        List<WorkflowInstanceRow> rows = mapper.selectAll();
        List<WorkflowInstance> instances = new ArrayList<>();
        for (WorkflowInstanceRow row : rows) {
            instances.add(fromRow(row));
        }
        return instances;
    }

    private WorkflowInstanceRow toRow(WorkflowInstance instance) {
        WorkflowInstanceRow row = new WorkflowInstanceRow();
        row.setProcessId(instance.getProcessId());
        row.setDomain(instance.getDomain());
        row.setBusinessId(instance.getBusinessId());
        row.setSubmitAction(instance.getSubmitAction());
        row.setStatus(instance.getStatus().name());
        row.setOperator(instance.getOperator());
        row.setCurrentNodeIndex(instance.getCurrentNodeIndex());
        row.setPayloadJson(toJson(instance.getPayload()));
        row.setNodesJson(toJson(instance.getNodes()));
        return row;
    }

    private WorkflowInstance fromRow(WorkflowInstanceRow row) {
        WorkflowInstance instance = new WorkflowInstance();
        instance.setProcessId(row.getProcessId());
        instance.setDomain(row.getDomain());
        instance.setBusinessId(row.getBusinessId());
        instance.setSubmitAction(row.getSubmitAction());
        instance.setStatus(WorkflowStatus.valueOf(row.getStatus()));
        instance.setOperator(row.getOperator());
        instance.setCurrentNodeIndex(row.getCurrentNodeIndex());
        instance.setPayload(fromJson(row.getPayloadJson(), Object.class));
        instance.setNodes(fromJson(row.getNodesJson(), new TypeReference<List<WorkflowNodeInstance>>() {
        }));
        return instance;
    }

    private String toJson(Object obj) {
        if (obj == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(obj);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to serialize to JSON", e);
        }
    }

    private <T> T fromJson(String json, Class<T> clazz) {
        if (json == null) {
            return null;
        }
        try {
            return objectMapper.readValue(json, clazz);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to deserialize from JSON", e);
        }
    }

    private <T> T fromJson(String json, TypeReference<T> typeRef) {
        if (json == null) {
            return null;
        }
        try {
            return objectMapper.readValue(json, typeRef);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to deserialize from JSON", e);
        }
    }
}
