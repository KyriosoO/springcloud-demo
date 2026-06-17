package com.dylan.employee.mapper;

import java.util.Map;
import java.util.StringJoiner;

import com.dylan.employee.model.Employee;

/**
 * 员工动态 SQL 构建器，生成更新和分页查询 SQL。
 */
public class EmployeeSqlProvider {
	private static final String TABLE = "employee";
	private static final String[] COLUMNS = {
			"ID_CARD_NO", "MEMBER_NO", "CHINESE_NAME", "FOREIGN_NAME", "DATE_OF_BIRTH", "GENDER",
			"MARITAL_STATUS", "PHONE_NO", "EMAIL", "ETHNIC_GROUP", "NATIONALITY", "ADDRESS_OF_DOMICILE",
			"DOMICILE_TYPE", "CONTACT_ADDRESS", "CA_ZIP_CODE", "REIMBURSEMENT_BANK", "REIMBURSEMENT_ACCOUNT",
			"REIMBURSEMENT_INST_CODE", "SALARY_BANK", "SALARY_ACCOUNT", "EI_NAME", "EI_RELATIONSHIP",
			"EI_TEL_NO", "EI_ADDRESS", "SW_PROPERTY", "SW_START_DATE", "FATHER_NAME", "FATHER_EMPLOYMENT",
			"FATHER_POSITION", "FATHER_TEL_NO", "FATHER_PHONE_NO", "IS_FATHER", "MOTHER_NAME",
			"MOTHER_EMPLOYMENT", "MOTHER_POSITION", "MOTHER_TEL_NO", "MOTHER_PHONE_NO", "IS_MOTHER",
			"SPOUSE_NAME", "SPOUSE_EMPLOYMENT", "SPOUSE_POSITION", "SPOUSE_TEL_NO", "SPOUSE_PHONE_NO",
			"IS_SPOUSE", "EDUCATION", "INSTITUTION", "MAJOR", "ACADEMIC_DEGREE", "ED_START_DATE",
			"ED_END_DATE", "SAP_CODE", "FILE_NAME", "OPER_TIME", "PUBLIC_EMAIL", "POSITION",
			"WORK_BASE_SI", "WORK_BASE_AF", "AF_ACCOUNT" };
	private static final String[] PROPERTIES = {
			"idCardNo", "memberNo", "chineseName", "foreignName", "dateOfBirth", "gender",
			"maritalStatus", "phoneNo", "email", "ethnicGroup", "nationality", "addressOfDomicile",
			"domicileType", "contactAddress", "caZipCode", "reimbursementBank", "reimbursementAccount",
			"reimbursementInstCode", "salaryBank", "salaryAccount", "eiName", "eiRelationship",
			"eiTelNo", "eiAddress", "swProperty", "swStartDate", "fatherName", "fatherEmployment",
			"fatherPosition", "fatherTelNo", "fatherPhoneNo", "isFather", "motherName",
			"motherEmployment", "motherPosition", "motherTelNo", "motherPhoneNo", "isMother",
			"spouseName", "spouseEmployment", "spousePosition", "spouseTelNo", "spousePhoneNo",
			"isSpouse", "education", "institution", "major", "academicDegree", "edStartDate",
			"edEndDate", "sapCode", "fileName", "operTime", "publicEmail", "position",
			"workBaseSi", "workBaseAf", "afAccount" };

	/**
	 * 处理 selectPage 相关逻辑。
	 */
	public String selectPage() {
		return "SELECT " + columnList() + " FROM " + TABLE + " LIMIT #{limit} OFFSET #{offset}";
	}

	/**
	 * 处理 selectSourcePage 相关逻辑。
	 */
	public String selectSourcePage() {
		return "SELECT " + columnList() + " FROM " + TABLE + sourceWhere() + " LIMIT #{limit} OFFSET #{offset}";
	}

	/**
	 * 统计业务数据数量。
	 */
	public String countSource() {
		return "SELECT COUNT(1) FROM " + TABLE + sourceWhere();
	}

	/**
	 * 处理 selectByIdCardNo 相关逻辑。
	 */
	public String selectByIdCardNo() {
		return "SELECT " + columnList() + " FROM " + TABLE + " WHERE ID_CARD_NO = #{idCardNo} LIMIT 1";
	}

	/**
	 * 统计业务数据数量。
	 */
	public String countAll() {
		return "SELECT COUNT(1) FROM " + TABLE;
	}

	/**
	 * 处理 insert 相关逻辑。
	 */
	public String insert(Map<String, Object> employee) {
		StringJoiner columns = new StringJoiner(", ");
		StringJoiner values = new StringJoiner(", ");
		for (int i = 0; i < COLUMNS.length; i++) {
			if (hasField(employee, i)) {
				columns.add(COLUMNS[i]);
				values.add(parameterRef(employee, i));
			}
		}
		return "INSERT INTO " + TABLE + " (" + columns + ") VALUES (" + values + ")";
	}

	/**
	 * 处理 updateByIdCardNo 相关逻辑。
	 */
	public String updateByIdCardNo(Map<String, Object> employee) {
		StringJoiner sets = new StringJoiner(", ");
		for (int i = 1; i < COLUMNS.length; i++) {
			if (hasField(employee, i)) {
				sets.add(COLUMNS[i] + " = " + parameterRef(employee, i));
			}
		}
		return "UPDATE " + TABLE + " SET " + sets + " WHERE ID_CARD_NO = #{idCardNo}";
	}

	/**
	 * 删除业务数据。
	 */
	public String deleteByIdCardNo() {
		return "DELETE FROM " + TABLE + " WHERE ID_CARD_NO = #{idCardNo}";
	}

	/**
	 * 处理 columnList 相关逻辑。
	 */
	private String columnList() {
		return String.join(", ", COLUMNS);
	}

	private boolean hasField(Map<String, Object> employee, int index) {
		return employee.containsKey(PROPERTIES[index]) || employee.containsKey(COLUMNS[index]);
	}

	private String parameterRef(Map<String, Object> employee, int index) {
		return "#{" + (employee.containsKey(PROPERTIES[index]) ? PROPERTIES[index] : COLUMNS[index]) + "}";
	}

	/**
	 * 提供索引源数据分页。
	 */
	private String sourceWhere() {
		return " WHERE (#{since} IS NULL OR #{since} = '' OR OPER_TIME >= #{since})";
	}
}
