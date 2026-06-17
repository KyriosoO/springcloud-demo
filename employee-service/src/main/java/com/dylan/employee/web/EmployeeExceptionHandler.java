package com.dylan.employee.web;

import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 员工服务异常处理器，统一转换业务异常响应。
 */
@RestControllerAdvice
public class EmployeeExceptionHandler {

	/**
	 * 处理 handleIllegalArgument 相关逻辑。
	 */
	@ExceptionHandler(IllegalArgumentException.class)
	public ResponseEntity<Map<String, String>> handleIllegalArgument(IllegalArgumentException e) {
		return ResponseEntity.badRequest().body(Map.of("message", e.getMessage()));
	}
}
