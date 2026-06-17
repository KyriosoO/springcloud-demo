package com.dylan.employee.dao;

import java.time.LocalDateTime;

/**
 * 数据库行映射 — employee_change_request 表。
 * 仅用于 Repository 内部，不暴露给 Service 层。
 */
public class EmployeeChangeRequestRow {
    private String changeRequestId;
    private String action;
    private String status;
    private String idCardNo;
    private String employeeJson;
    private String applicant;
    private String approvalProcessId;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    public String getChangeRequestId() {
        return changeRequestId;
    }

    public void setChangeRequestId(String changeRequestId) {
        this.changeRequestId = changeRequestId;
    }

    public String getAction() {
        return action;
    }

    public void setAction(String action) {
        this.action = action;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getIdCardNo() {
        return idCardNo;
    }

    public void setIdCardNo(String idCardNo) {
        this.idCardNo = idCardNo;
    }

    public String getEmployeeJson() {
        return employeeJson;
    }

    public void setEmployeeJson(String employeeJson) {
        this.employeeJson = employeeJson;
    }

    public String getApplicant() {
        return applicant;
    }

    public void setApplicant(String applicant) {
        this.applicant = applicant;
    }

    public String getApprovalProcessId() {
        return approvalProcessId;
    }

    public void setApprovalProcessId(String approvalProcessId) {
        this.approvalProcessId = approvalProcessId;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }
}
