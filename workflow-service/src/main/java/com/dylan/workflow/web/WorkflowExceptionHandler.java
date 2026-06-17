package com.dylan.workflow.web;

import java.util.Map;
import java.util.NoSuchElementException;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import com.dylan.workflow.engine.WorkflowTodoChangedException;

@RestControllerAdvice
public class WorkflowExceptionHandler {

	@ExceptionHandler(NoSuchElementException.class)
	@ResponseStatus(HttpStatus.NOT_FOUND)
	public Map<String, String> handleNotFound(NoSuchElementException e) {
		return Map.of("message", e.getMessage());
	}

	@ExceptionHandler({ IllegalArgumentException.class, IllegalStateException.class })
	@ResponseStatus(HttpStatus.BAD_REQUEST)
	public Map<String, String> handleBadRequest(RuntimeException e) {
		return Map.of("message", e.getMessage());
	}

	@ExceptionHandler(WorkflowTodoChangedException.class)
	@ResponseStatus(HttpStatus.CONFLICT)
	public Map<String, String> handleTodoChanged(WorkflowTodoChangedException e) {
		return Map.of("code", "TODO_CHANGED", "message", e.getMessage());
	}
}
