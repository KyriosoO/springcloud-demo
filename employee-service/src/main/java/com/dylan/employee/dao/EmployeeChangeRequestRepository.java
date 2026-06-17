package com.dylan.employee.dao;

import java.util.Map;
import java.util.NoSuchElementException;

import org.springframework.stereotype.Repository;

import com.dylan.employee.model.Employee;
import com.dylan.employee.model.EmployeeChangeAction;
import com.dylan.employee.model.EmployeeChangeRequest;
import com.dylan.employee.model.EmployeeChangeStatus;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * 数据库版员工变更申请仓库，是 EmployeeChangeRequest 的唯一持久化边界。
 */
@Repository
public class EmployeeChangeRequestRepository {

	private final EmployeeChangeRequestMapper mapper;
	private final ObjectMapper objectMapper;

	public EmployeeChangeRequestRepository(EmployeeChangeRequestMapper mapper, ObjectMapper objectMapper) {
		this.mapper = mapper;
		this.objectMapper = objectMapper;
	}

	public void save(EmployeeChangeRequest request) {
		mapper.upsert(toRow(request));
	}

	public EmployeeChangeRequest findById(String changeRequestId) {
		EmployeeChangeRequestRow row = mapper.selectById(changeRequestId);
		if (row == null) {
			throw new NoSuchElementException("Employee change request not found: " + changeRequestId);
		}
		return fromRow(row);
	}

	public void updateStatus(String changeRequestId, EmployeeChangeStatus status) {
		mapper.updateStatus(changeRequestId, status.name());
	}

	private EmployeeChangeRequestRow toRow(EmployeeChangeRequest request) {
		EmployeeChangeRequestRow row = new EmployeeChangeRequestRow();
		row.setChangeRequestId(request.getChangeRequestId());
		row.setAction(request.getAction().name());
		row.setStatus(request.getStatus().name());
		row.setIdCardNo(request.getIdCardNo());
		row.setEmployeeJson(toJson(request.getEmployee()));
		row.setApplicant(request.getApplicant());
		row.setApprovalProcessId(request.getApprovalProcessId());
		return row;
	}

	private EmployeeChangeRequest fromRow(EmployeeChangeRequestRow row) {
		EmployeeChangeRequest request = new EmployeeChangeRequest();
		request.setChangeRequestId(row.getChangeRequestId());
		request.setAction(EmployeeChangeAction.valueOf(row.getAction()));
		request.setStatus(EmployeeChangeStatus.valueOf(row.getStatus()));
		request.setIdCardNo(row.getIdCardNo());
		request.setEmployee(fromJson(row.getEmployeeJson(), new TypeReference<Map<String, Object>>() {
		}));
		request.setApplicant(row.getApplicant());
		request.setApprovalProcessId(row.getApprovalProcessId());
		return request;
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

	private <T> T fromJson(String json, TypeReference<T> type) {
		if (json == null) {
			return null;
		}
		try {
			return objectMapper.readValue(json, type);
		} catch (JsonProcessingException e) {
			throw new RuntimeException("Failed to deserialize from JSON", e);
		}
	}
}
