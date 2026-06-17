package com.dylan.employee.controller;

import java.util.List;
import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.dylan.employee.model.Employee;
import com.dylan.employee.model.EmployeeChangeRequest;
import com.dylan.employee.service.EmployeeService;
import com.dylan.employee.web.EmployeeChangeSubmitResponse;

@RestController
@RequestMapping("/employees")
public class EmployeeController {
	private final EmployeeService employeeService;

	public EmployeeController(EmployeeService employeeService) {
		this.employeeService = employeeService;
	}

	@GetMapping
	public List<Employee> page(@RequestParam(defaultValue = "1") int page,
			@RequestParam(defaultValue = "20") int size) {
		return employeeService.page(page, size);
	}

	@GetMapping("/{idCardNo}")
	public Employee detail(@PathVariable String idCardNo) {
		return employeeService.detail(idCardNo);
	}

	@GetMapping("/count")
	public long count() {
		return employeeService.count();
	}

	@PostMapping
	@ResponseStatus(HttpStatus.ACCEPTED)
	public EmployeeChangeSubmitResponse create(@RequestBody Map<String, Object> employee,
			@RequestParam(defaultValue = "system") String operator) {
		return employeeService.create(employee, operator);
	}

	@PutMapping("/{idCardNo}")
	@ResponseStatus(HttpStatus.ACCEPTED)
	public EmployeeChangeSubmitResponse update(@PathVariable String idCardNo, @RequestBody Map<String, Object> employee,
			@RequestParam(defaultValue = "system") String operator) {
		return employeeService.update(idCardNo, employee, operator);
	}

	@GetMapping("/change-requests/{changeRequestId}")
	public EmployeeChangeRequest changeRequestDetail(@PathVariable String changeRequestId) {
		return employeeService.changeRequestDetail(changeRequestId);
	}

	@DeleteMapping("/{idCardNo}")
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void delete(@PathVariable String idCardNo) {
		employeeService.delete(idCardNo);
	}
}
