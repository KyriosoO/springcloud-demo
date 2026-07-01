package com.dylan.authcenter.model;

import java.util.Map;

public class LoginRequest {
	private String userId;
	private String password;

	public String getUserId() {
		return userId;
	}

	public void setUserId(String userId) {
		this.userId = userId;
	}

	public String getPassword() {
		return password;
	}

	public void setPassword(String password) {
		this.password = password;
	}

	public LoginRequest getLoginRequest(Map<String,String> map) {
		setPassword(map.get("password"));
		setUserId(map.get("userId"));
		return this;
	}
}
