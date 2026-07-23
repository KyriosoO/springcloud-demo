package com.dylan.agent.employee.api;

import org.springframework.http.HttpStatus;

public final class AgentBusinessException extends RuntimeException {
	private final String code;
	private final HttpStatus status;
	private final String requestId;

	public AgentBusinessException(String code, HttpStatus status) {
		this(code, status, "");
	}

	public AgentBusinessException(String code, HttpStatus status, String requestId) {
		super(code);
		this.code = code;
		this.status = status;
		this.requestId = requestId == null ? "" : requestId;
	}

	public String code() { return code; }
	public HttpStatus status() { return status; }
	public String requestId() { return requestId; }
}
