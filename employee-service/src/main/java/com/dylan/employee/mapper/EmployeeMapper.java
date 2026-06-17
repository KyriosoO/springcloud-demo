package com.dylan.employee.mapper;

import java.util.List;
import java.util.Map;

import org.apache.ibatis.annotations.DeleteProvider;
import org.apache.ibatis.annotations.InsertProvider;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.ResultMap;
import org.apache.ibatis.annotations.Result;
import org.apache.ibatis.annotations.Results;
import org.apache.ibatis.annotations.SelectProvider;
import org.apache.ibatis.annotations.UpdateProvider;

import com.dylan.employee.model.Employee;

/**
 * 员工数据库访问接口，定义员工数据持久化操作。
 */
@Mapper
public interface EmployeeMapper {

	/**
	 * 分页查询员工数据。
	 */
	@SelectProvider(type = EmployeeSqlProvider.class, method = "selectPage")
	@Results(id = "EmployeeResultMap", value = { @Result(property = "idCardNo", column = "ID_CARD_NO"),
			@Result(property = "memberNo", column = "MEMBER_NO"),
			@Result(property = "chineseName", column = "CHINESE_NAME"),
			@Result(property = "foreignName", column = "FOREIGN_NAME"),
			@Result(property = "dateOfBirth", column = "DATE_OF_BIRTH"),
			@Result(property = "gender", column = "GENDER"),
			@Result(property = "maritalStatus", column = "MARITAL_STATUS"),
			@Result(property = "phoneNo", column = "PHONE_NO"), @Result(property = "email", column = "EMAIL"),
			@Result(property = "ethnicGroup", column = "ETHNIC_GROUP"),
			@Result(property = "nationality", column = "NATIONALITY"),
			@Result(property = "addressOfDomicile", column = "ADDRESS_OF_DOMICILE"),
			@Result(property = "domicileType", column = "DOMICILE_TYPE"),
			@Result(property = "contactAddress", column = "CONTACT_ADDRESS"),
			@Result(property = "caZipCode", column = "CA_ZIP_CODE"),
			@Result(property = "reimbursementBank", column = "REIMBURSEMENT_BANK"),
			@Result(property = "reimbursementAccount", column = "REIMBURSEMENT_ACCOUNT"),
			@Result(property = "reimbursementInstCode", column = "REIMBURSEMENT_INST_CODE"),
			@Result(property = "salaryBank", column = "SALARY_BANK"),
			@Result(property = "salaryAccount", column = "SALARY_ACCOUNT"),
			@Result(property = "eiName", column = "EI_NAME"),
			@Result(property = "eiRelationship", column = "EI_RELATIONSHIP"),
			@Result(property = "eiTelNo", column = "EI_TEL_NO"), @Result(property = "eiAddress", column = "EI_ADDRESS"),
			@Result(property = "swProperty", column = "SW_PROPERTY"),
			@Result(property = "swStartDate", column = "SW_START_DATE"),
			@Result(property = "fatherName", column = "FATHER_NAME"),
			@Result(property = "fatherEmployment", column = "FATHER_EMPLOYMENT"),
			@Result(property = "fatherPosition", column = "FATHER_POSITION"),
			@Result(property = "fatherTelNo", column = "FATHER_TEL_NO"),
			@Result(property = "fatherPhoneNo", column = "FATHER_PHONE_NO"),
			@Result(property = "isFather", column = "IS_FATHER"),
			@Result(property = "motherName", column = "MOTHER_NAME"),
			@Result(property = "motherEmployment", column = "MOTHER_EMPLOYMENT"),
			@Result(property = "motherPosition", column = "MOTHER_POSITION"),
			@Result(property = "motherTelNo", column = "MOTHER_TEL_NO"),
			@Result(property = "motherPhoneNo", column = "MOTHER_PHONE_NO"),
			@Result(property = "isMother", column = "IS_MOTHER"),
			@Result(property = "spouseName", column = "SPOUSE_NAME"),
			@Result(property = "spouseEmployment", column = "SPOUSE_EMPLOYMENT"),
			@Result(property = "spousePosition", column = "SPOUSE_POSITION"),
			@Result(property = "spouseTelNo", column = "SPOUSE_TEL_NO"),
			@Result(property = "spousePhoneNo", column = "SPOUSE_PHONE_NO"),
			@Result(property = "isSpouse", column = "IS_SPOUSE"), @Result(property = "education", column = "EDUCATION"),
			@Result(property = "institution", column = "INSTITUTION"), @Result(property = "major", column = "MAJOR"),
			@Result(property = "academicDegree", column = "ACADEMIC_DEGREE"),
			@Result(property = "edStartDate", column = "ED_START_DATE"),
			@Result(property = "edEndDate", column = "ED_END_DATE"), @Result(property = "sapCode", column = "SAP_CODE"),
			@Result(property = "fileName", column = "FILE_NAME"), @Result(property = "operTime", column = "OPER_TIME"),
			@Result(property = "publicEmail", column = "PUBLIC_EMAIL"),
			@Result(property = "position", column = "POSITION"),
			@Result(property = "workBaseSi", column = "WORK_BASE_SI"),
			@Result(property = "workBaseAf", column = "WORK_BASE_AF"),
			@Result(property = "afAccount", column = "AF_ACCOUNT") })
	List<Employee> selectPage(@Param("offset") int offset, @Param("limit") int limit);

	/**
	 * 按身份证号查询员工详情。
	 */
	@SelectProvider(type = EmployeeSqlProvider.class, method = "selectByIdCardNo")
	@ResultMap("EmployeeResultMap")
	Employee selectByIdCardNo(@Param("idCardNo") String idCardNo);

	/**
	 * 查询用于索引同步的员工分页数据。
	 */
	@SelectProvider(type = EmployeeSqlProvider.class, method = "selectSourcePage")
	@ResultMap("EmployeeResultMap")
	List<Employee> selectSourcePage(@Param("since") String since, @Param("offset") int offset,
			@Param("limit") int limit);

	/**
	 * 统计全部员工数量。
	 */
	@SelectProvider(type = EmployeeSqlProvider.class, method = "countAll")
	long countAll();

	/**
	 * 统计指定时间之后发生变化的员工数量。
	 */
	@SelectProvider(type = EmployeeSqlProvider.class, method = "countSource")
	long countSource(@Param("since") String since);

	/**
	 * 新增员工记录。
	 */
	@InsertProvider(type = EmployeeSqlProvider.class, method = "insert")
	int insert(Map<String, Object> employee);

	/**
	 * 按身份证号更新员工记录。
	 */
	@UpdateProvider(type = EmployeeSqlProvider.class, method = "updateByIdCardNo")
	int updateByIdCardNo(Map<String, Object> employee);

	/**
	 * 按身份证号删除员工记录。
	 */
	@DeleteProvider(type = EmployeeSqlProvider.class, method = "deleteByIdCardNo")
	int deleteByIdCardNo(@Param("idCardNo") String idCardNo);
}
