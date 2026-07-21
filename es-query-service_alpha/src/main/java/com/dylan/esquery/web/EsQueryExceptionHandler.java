package com.dylan.esquery.web;

import java.io.IOException;
import java.util.Map;

import org.elasticsearch.client.ResponseException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * ES 查询服务异常处理器，统一转换异常响应。
 */
@RestControllerAdvice
public class EsQueryExceptionHandler {

	/**
	 * 处理 handleBadRequest 相关逻辑。
	 */
	@ExceptionHandler(IllegalArgumentException.class)
	public ResponseEntity<Map<String, String>> handleBadRequest(IllegalArgumentException e) {
		return ResponseEntity.badRequest().body(Map.of("message", e.getMessage()));
	}

	/**
	 * 处理 handleEsResponse 相关逻辑。
	 */
	@ExceptionHandler(ResponseException.class)
	public ResponseEntity<Map<String, String>> handleEsResponse(ResponseException e) {
		int statusCode = e.getResponse().getStatusLine().getStatusCode();
		return ResponseEntity.status(statusCode).body(Map.of("message", e.getMessage()));
	}

	/**
	 * 处理 handleIo 相关逻辑。
	 */
	@ExceptionHandler(IOException.class)
	public ResponseEntity<Map<String, String>> handleIo(IOException e) {
		return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(Map.of("message", e.getMessage()));
	}
}
