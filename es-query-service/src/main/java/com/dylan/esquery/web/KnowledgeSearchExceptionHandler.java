package com.dylan.esquery.web;

import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import com.dylan.esquery.controller.KnowledgeSearchController;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeAuthorityUnavailableException;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeForbiddenException;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeInvalidRequestException;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeProviderException;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeRateLimitedException;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeTimeoutException;

@RestControllerAdvice(assignableTypes = KnowledgeSearchController.class)
public class KnowledgeSearchExceptionHandler {

	@ExceptionHandler(KnowledgeInvalidRequestException.class)
	ResponseEntity<Map<String, Object>> invalid() { return error(HttpStatus.BAD_REQUEST, "INVALID_REQUEST"); }

	@ExceptionHandler(KnowledgeForbiddenException.class)
	ResponseEntity<Map<String, Object>> forbidden() { return error(HttpStatus.FORBIDDEN, "FORBIDDEN"); }

	@ExceptionHandler(KnowledgeAuthorityUnavailableException.class)
	ResponseEntity<Map<String, Object>> authorityUnavailable() {
		return error(HttpStatus.SERVICE_UNAVAILABLE, "READ_AUTHORITY_UNAVAILABLE");
	}

	@ExceptionHandler(KnowledgeRateLimitedException.class)
	ResponseEntity<Map<String, Object>> rateLimited() { return error(HttpStatus.TOO_MANY_REQUESTS, "RATE_LIMITED"); }

	@ExceptionHandler(KnowledgeTimeoutException.class)
	ResponseEntity<Map<String, Object>> timeout() { return error(HttpStatus.GATEWAY_TIMEOUT, "TIMEOUT"); }

	@ExceptionHandler(KnowledgeProviderException.class)
	ResponseEntity<Map<String, Object>> provider() { return error(HttpStatus.BAD_GATEWAY, "PROVIDER_FAILURE"); }

	private static ResponseEntity<Map<String, Object>> error(HttpStatus status, String code) {
		return ResponseEntity.status(status).body(Map.of("schemaVersion", 1, "code", code));
	}
}
