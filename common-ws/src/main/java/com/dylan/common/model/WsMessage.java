package com.dylan.common.model;

public class WsMessage<T> {
	private String type; // 业务类型：ORDER / STOCK / NOTICE
	private String userId;
	private T data; // 泛型数据

	public String getType() {
		return type;
	}

	public void setType(String type) {
		this.type = type;
	}

	public String getUserId() {
		return userId;
	}

	public void setUserId(String userId) {
		this.userId = userId;
	}

	public T getData() {
		return data;
	}

	public void setData(T data) {
		this.data = data;
	}
}
