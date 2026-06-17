package com.dylan.employee.dao;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface EmployeeChangeRequestMapper {

    @Insert("INSERT INTO employee_change_request (change_request_id, action, status, id_card_no, employee_json, applicant, approval_process_id) "
            + "VALUES (#{changeRequestId}, #{action}, #{status}, #{idCardNo}, #{employeeJson}, #{applicant}, #{approvalProcessId}) "
            + "ON DUPLICATE KEY UPDATE action = VALUES(action), status = VALUES(status), "
            + "id_card_no = VALUES(id_card_no), employee_json = VALUES(employee_json), "
            + "applicant = VALUES(applicant), approval_process_id = VALUES(approval_process_id), "
            + "updated_at = NOW()")
    void upsert(EmployeeChangeRequestRow row);

    @Select("SELECT change_request_id, action, status, id_card_no, employee_json AS employeeJson, "
            + "applicant, approval_process_id AS approvalProcessId, created_at AS createdAt, updated_at AS updatedAt "
            + "FROM employee_change_request WHERE change_request_id = #{changeRequestId}")
    EmployeeChangeRequestRow selectById(String changeRequestId);

    @Update("UPDATE employee_change_request SET status = #{status}, updated_at = NOW() "
            + "WHERE change_request_id = #{changeRequestId}")
    int updateStatus(@Param("changeRequestId") String changeRequestId, @Param("status") String status);
}
