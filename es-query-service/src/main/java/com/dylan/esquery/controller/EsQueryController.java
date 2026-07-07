package com.dylan.esquery.controller;

import java.io.IOException;
import java.util.Collection;

import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.dylan.esquery.api.model.BulkIndexRequest;
import com.dylan.esquery.api.model.AliasSwitchRequest;
import com.dylan.esquery.api.model.HybridSearchRequest;
import com.dylan.esquery.api.model.HybridSearchResponse;
import com.dylan.esquery.api.model.IndexDocumentRequest;
import com.dylan.esquery.api.model.RebuildRequest;
import com.dylan.esquery.api.model.RebuildTask;
import com.dylan.esquery.api.model.VectorSearchRequest;
import com.dylan.esquery.service.EsDocumentService;
import com.dylan.esquery.service.EsIndexAliasService;
import com.dylan.esquery.service.EsManagementAccessGuard;
import com.dylan.esquery.service.IndexRebuildService;
import com.dylan.esquery.service.RebuildTaskRepository;

/**
 * ES 查询控制器，提供索引、检索、删除和重建接口。
 */
@RestController
@RequestMapping("/es")
public class EsQueryController {
	private final EsDocumentService esDocumentService;
	private final IndexRebuildService indexRebuildService;
	private final RebuildTaskRepository taskRepository;
	private final EsIndexAliasService aliasService;
	private final EsManagementAccessGuard managementAccessGuard;

	/**
	 * 创建 EsQueryController 实例并注入所需依赖。
	 */
	public EsQueryController(EsDocumentService esDocumentService, IndexRebuildService indexRebuildService,
			RebuildTaskRepository taskRepository,
			EsIndexAliasService aliasService,
			EsManagementAccessGuard managementAccessGuard) {
		this.esDocumentService = esDocumentService;
		this.indexRebuildService = indexRebuildService;
		this.taskRepository = taskRepository;
		this.aliasService = aliasService;
		this.managementAccessGuard = managementAccessGuard;
	}

	/**
	 * 执行领域搜索。
	 */
	@PostMapping(value = "/indexes/{index}/search", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
	public ResponseEntity<String> search(@PathVariable String index, @RequestBody String queryDsl) throws IOException {
		return ResponseEntity.ok(esDocumentService.search(index, queryDsl));
	}

	/**
	 * 处理 indexDocument 相关逻辑。
	 */
	@PutMapping(value = "/indexes/{index}/documents", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
	public ResponseEntity<String> indexDocument(@PathVariable String index, @RequestBody IndexDocumentRequest request)
			throws IOException {
		return ResponseEntity.ok(esDocumentService.indexDocument(index, request.getId(), request.getDocument()));
	}

	/**
	 * 删除业务数据。
	 */
	@DeleteMapping(value = "/indexes/{index}/documents/{id}", produces = MediaType.APPLICATION_JSON_VALUE)
	public ResponseEntity<String> deleteDocument(@PathVariable String index, @PathVariable String id)
			throws IOException {
		return ResponseEntity.ok(esDocumentService.deleteDocument(index, id));
	}

	/**
	 * 批量处理索引文档。
	 */
	@PostMapping(value = "/indexes/{index}/bulk", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
	public ResponseEntity<String> bulkIndex(@PathVariable String index, @RequestBody BulkIndexRequest request)
			throws IOException {
		return ResponseEntity.ok(esDocumentService.bulkIndex(index, request.getIdField(), request.getDocuments()));
	}

	/**
	 * 处理 fullRebuild 相关逻辑。
	 */
	@PostMapping("/indexes/{index}/rebuild/full")
	@ResponseStatus(HttpStatus.ACCEPTED)
	public RebuildTask fullRebuild(
			@PathVariable String index,
			@RequestBody RebuildRequest request,
			@RequestHeader(value = EsManagementAccessGuard.TOKEN_HEADER, required = false) String serviceToken) {
		managementAccessGuard.requireServiceToken(serviceToken);
		return indexRebuildService.submitFullRebuild(index, request);
	}

	/**
	 * 处理 incrementalRebuild 相关逻辑。
	 */
	@PostMapping("/indexes/{index}/rebuild/incremental")
	@ResponseStatus(HttpStatus.ACCEPTED)
	public RebuildTask incrementalRebuild(
			@PathVariable String index,
			@RequestBody RebuildRequest request,
			@RequestHeader(value = EsManagementAccessGuard.TOKEN_HEADER, required = false) String serviceToken) {
		managementAccessGuard.requireServiceToken(serviceToken);
		return indexRebuildService.submitIncrementalRebuild(index, request);
	}

	/**
	 * 处理 task 相关逻辑。
	 */
	@GetMapping("/rebuild/tasks/{taskId}")
	public RebuildTask task(
			@PathVariable String taskId,
			@RequestHeader(value = EsManagementAccessGuard.TOKEN_HEADER, required = false) String serviceToken) {
		managementAccessGuard.requireServiceToken(serviceToken);
		return taskRepository.findById(taskId);
	}

	/**
	 * 处理 tasks 相关逻辑。
	 */
	@GetMapping("/rebuild/tasks")
	public Collection<RebuildTask> tasks(
			@RequestHeader(value = EsManagementAccessGuard.TOKEN_HEADER, required = false) String serviceToken) {
		managementAccessGuard.requireServiceToken(serviceToken);
		return taskRepository.findAll();
	}

	/**
	 * 向量查询
	 * @param index
	 * @param request
	 * @return
	 * @throws IOException
	 */
	@PostMapping(value = "/indexes/{index}/vector-search", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
	public ResponseEntity<String> vectorSearch(@PathVariable String index, @RequestBody VectorSearchRequest request)
			throws IOException {
		return ResponseEntity.ok(esDocumentService.vectorSearch(index, request));
	}

	/**
	 * 混合检索。请求中的 queryVector 必须由上游生成，本服务只做召回和 RRF 融合。
	 */
	@PostMapping(value = "/indexes/{index}/hybrid-search", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
	public ResponseEntity<HybridSearchResponse> hybridSearch(
			@PathVariable String index,
			@RequestBody HybridSearchRequest request) throws IOException {
		return ResponseEntity.ok(esDocumentService.hybridSearch(index, request));
	}

	@PostMapping(value = "/indexes/{index}/aliases/read/switch", consumes = MediaType.APPLICATION_JSON_VALUE)
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void switchReadAlias(
			@PathVariable String index,
			@RequestBody AliasSwitchRequest request,
			@RequestHeader(value = EsManagementAccessGuard.TOKEN_HEADER, required = false) String serviceToken)
			throws IOException {
		managementAccessGuard.requireServiceToken(serviceToken);
		aliasService.switchReadAlias(index, request);
	}

	@PostMapping(value = "/indexes/{index}/aliases/read/rollback", consumes = MediaType.APPLICATION_JSON_VALUE)
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void rollbackReadAlias(
			@PathVariable String index,
			@RequestBody AliasSwitchRequest request,
			@RequestHeader(value = EsManagementAccessGuard.TOKEN_HEADER, required = false) String serviceToken)
			throws IOException {
		managementAccessGuard.requireServiceToken(serviceToken);
		aliasService.rollbackReadAlias(index, request);
	}

}
