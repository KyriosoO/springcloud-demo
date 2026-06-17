package com.dylan.employee.es;

import java.util.Collection;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;

import com.dylan.esquery.api.model.BulkIndexRequest;
import com.dylan.esquery.api.model.IndexDocumentRequest;
import com.dylan.esquery.api.model.RebuildRequest;
import com.dylan.esquery.api.model.RebuildTask;
import com.dylan.esquery.api.model.VectorSearchRequest;

/**
 * ES 查询服务客户端，封装员工服务对 es-query-service 的调用。
 */
@FeignClient(name = "es-query-service", path = "/es", contextId = "employee2esQuery")
public interface EsQueryClient {

	/**
	 * 调用 ES 查询服务执行查询 DSL 检索。
	 */
	@PostMapping(value = "/indexes/{index}/search", consumes = MediaType.APPLICATION_JSON_VALUE)
	String search(@PathVariable("index") String index, @RequestBody String queryDsl);

	/**
	 * 调用 ES 查询服务执行向量检索。
	 */
	@PostMapping(value = "/indexes/{index}/vector-search", consumes = MediaType.APPLICATION_JSON_VALUE)
	String vectorSearch(@PathVariable("index") String index, @RequestBody VectorSearchRequest request);

	/**
	 * 写入或更新单个索引文档。
	 */
	@PutMapping(value = "/indexes/{index}/documents", consumes = MediaType.APPLICATION_JSON_VALUE)
	String indexDocument(@PathVariable("index") String index, @RequestBody IndexDocumentRequest request);

	/**
	 * 删除指定索引文档。
	 */
	@DeleteMapping(value = "/indexes/{index}/documents/{id}")
	String deleteDocument(@PathVariable("index") String index, @PathVariable("id") String id);

	/**
	 * 批量写入索引文档。
	 */
	@PostMapping(value = "/indexes/{index}/bulk", consumes = MediaType.APPLICATION_JSON_VALUE)
	String bulkIndex(@PathVariable("index") String index, @RequestBody BulkIndexRequest request);

	/**
	 * 发起全量索引重建任务。
	 */
	@PostMapping(value = "/indexes/{index}/rebuild/full", consumes = MediaType.APPLICATION_JSON_VALUE)
	RebuildTask fullRebuild(@PathVariable("index") String index, @RequestBody RebuildRequest request);

	/**
	 * 发起增量索引重建任务。
	 */
	@PostMapping(value = "/indexes/{index}/rebuild/incremental", consumes = MediaType.APPLICATION_JSON_VALUE)
	RebuildTask incrementalRebuild(@PathVariable("index") String index, @RequestBody RebuildRequest request);

	/**
	 * 查询单个索引重建任务。
	 */
	@GetMapping("/rebuild/tasks/{taskId}")
	RebuildTask task(@PathVariable("taskId") String taskId);

	/**
	 * 查询全部索引重建任务。
	 */
	@GetMapping("/rebuild/tasks")
	Collection<RebuildTask> tasks();
}
