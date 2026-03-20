package com.dylan.authCenter.model;

import java.util.Map;

public class LoginRequest {
	private String username;
	private String password;

	public String getUsername() {
		return username;
	}

	public void setUsername(String username) {
		this.username = username;
	}

	public String getPassword() {
		return password;
	}

	public void setPassword(String password) {
		this.password = password;
	}

	public LoginRequest getLoginRequest(Map<String,String> map) {
		setPassword(map.get("password"));
		setUsername(map.get("username"));
		return this;
	}
}
