package com.dylan.employee.controller;

import java.util.Collection;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.security.core.Authentication;

import com.dylan.employee.es.EmployeeRebuildRequest;
import com.dylan.employee.security.CapabilityAccessGuard;
import com.dylan.esquery.api.model.SearchRequest;
import com.dylan.esquery.api.model.SemanticSearchRequest;
import com.dylan.esquery.api.model.RebuildTask;
import com.dylan.employee.service.EmployeeEsService;
import com.fasterxml.jackson.core.JsonProcessingException;

/**
 * 员工 Elasticsearch 控制器，提供索引重建和检索接口。
 */
@RestController
@RequestMapping("/employees/es")
public class EmployeeEsController {
	private final EmployeeEsService employeeEsService;
	private final CapabilityAccessGuard accessGuard;

	/**
	 * 创建 EmployeeEsController 实例并注入所需依赖。
	 */
	public EmployeeEsController(EmployeeEsService employeeEsService, CapabilityAccessGuard accessGuard) {
		this.employeeEsService = employeeEsService;
		this.accessGuard = accessGuard;
	}

	/**
	 * 执行领域搜索。
	 */
	@PostMapping("/search")
	public String search(Authentication authentication, @RequestBody SearchRequest request)
			throws JsonProcessingException {
		accessGuard.requireUserOrAgentScope(authentication, "agent.employee.query");
		return employeeEsService.search(request);
	}

	/**
	 * 执行向量检索逻辑。
	 */
	@PostMapping("/vector-search")
	public String vectorSearch(Authentication authentication, @RequestBody SemanticSearchRequest request) {
		accessGuard.requireUserOrAgentScope(authentication, "agent.employee.vector-search");
		return employeeEsService.vectorSearch(request);
	}

	/**
	 * 处理 indexOne 相关逻辑。
	 */
	@PostMapping("/documents/{idCardNo}")
	public String indexOne(@PathVariable String idCardNo,
			@RequestParam(required = false) String embeddingField,
			@RequestParam(required = false) Integer embeddingDims) {
		return employeeEsService.indexOne(idCardNo, embeddingField, embeddingDims);
	}

	/**
	 * 删除业务数据。
	 */
	@DeleteMapping("/documents/{idCardNo}")
	public String deleteOne(@PathVariable String idCardNo) {
		return employeeEsService.deleteOne(idCardNo);
	}

	/**
	 * 批量处理索引文档。
	 */
	@PostMapping("/bulk")
	public String bulkIndex(@RequestParam(defaultValue = "1") int page,
			@RequestParam(defaultValue = "500") int size,
			@RequestParam(required = false) String embeddingField,
			@RequestParam(required = false) Integer embeddingDims) {
		return employeeEsService.bulkIndex(page, size, embeddingField, embeddingDims);
	}

	/**
	 * 处理 fullRebuild 相关逻辑。
	 */
	@PostMapping("/rebuild/full")
	public RebuildTask fullRebuild(@RequestBody(required = false) EmployeeRebuildRequest request) {
		return employeeEsService.fullRebuild(request);
	}

	/**
	 * 处理 incrementalRebuild 相关逻辑。
	 */
	@PostMapping("/rebuild/incremental")
	public RebuildTask incrementalRebuild(@RequestBody(required = false) EmployeeRebuildRequest request) {
		return employeeEsService.incrementalRebuild(request);
	}

	/**
	 * 处理 task 相关逻辑。
	 */
	@GetMapping("/rebuild/tasks/{taskId}")
	public RebuildTask task(@PathVariable String taskId) {
		return employeeEsService.task(taskId);
	}

	/**
	 * 处理 tasks 相关逻辑。
	 */
	@GetMapping("/rebuild/tasks")
	public Collection<RebuildTask> tasks() {
		return employeeEsService.tasks();
	}
}
