package com.dylan.employee.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.dylan.esquery.api.model.SourcePageResponse;
import com.dylan.employee.service.EmployeeService;

/**
 * 员工 ES 数据源控制器，为索引服务提供分页源数据。
 */
@RestController
@RequestMapping("/internal/es/employees")
public class EmployeeEsSourceController {
	private final EmployeeService employeeService;

	/**
	 * 创建 EmployeeEsSourceController 实例并注入所需依赖。
	 */
	public EmployeeEsSourceController(EmployeeService employeeService) {
		this.employeeService = employeeService;
	}

	/**
	 * 分页查询业务数据。
	 */
	@GetMapping
	public SourcePageResponse page(@RequestParam(required = false) String since,
			@RequestParam(required = false) String cursor,
			@RequestParam(required = false) Integer batchSize,
			@RequestParam(required = false) String embeddingField,
			@RequestParam(required = false) Integer embeddingDims) {
		return employeeService.sourcePage(since, cursor, batchSize, embeddingField, embeddingDims);
	}
}
