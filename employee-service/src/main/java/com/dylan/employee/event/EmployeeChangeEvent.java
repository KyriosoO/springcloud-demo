package com.dylan.employee.event;

import java.io.Serializable;
import java.time.Instant;

/**
 * 员工数据变更事件，描述员工数据新增、更新或删除。
 */
public class EmployeeChangeEvent implements Serializable {
	private static final long serialVersionUID = 1L;

	public static final String TYPE_UPSERT = "UPSERT";
	public static final String TYPE_DELETE = "DELETE";

	private String eventType;
	private String idCardNo;
	private String occurredAt;

	/**
	 * 写入或更新索引文档。
	 */
	public static EmployeeChangeEvent upsert(String idCardNo) {
		return of(TYPE_UPSERT, idCardNo);
	}

	/**
	 * 删除业务数据。
	 */
	public static EmployeeChangeEvent delete(String idCardNo) {
		return of(TYPE_DELETE, idCardNo);
	}

	/**
	 * 处理 of 相关逻辑。
	 */
	private static EmployeeChangeEvent of(String eventType, String idCardNo) {
		EmployeeChangeEvent event = new EmployeeChangeEvent();
		event.setEventType(eventType);
		event.setIdCardNo(idCardNo);
		event.setOccurredAt(Instant.now().toString());
		return event;
	}

	public String getEventType() {
		return eventType;
	}

	public void setEventType(String eventType) {
		this.eventType = eventType;
	}

	public String getIdCardNo() {
		return idCardNo;
	}

	public void setIdCardNo(String idCardNo) {
		this.idCardNo = idCardNo;
	}

	public String getOccurredAt() {
		return occurredAt;
	}

	public void setOccurredAt(String occurredAt) {
		this.occurredAt = occurredAt;
	}
}
