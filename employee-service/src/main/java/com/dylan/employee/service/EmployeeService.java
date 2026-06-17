package com.dylan.employee.service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.dylan.employee.event.EmployeeChangeEventPublisher;
import com.dylan.employee.approval.ApprovalGateway;
import com.dylan.employee.dao.EmployeeChangeRequestRepository;
import com.dylan.employee.dao.EmployeeWorkflowInboxRepository;
import com.dylan.employee.mapper.EmployeeMapper;
import com.dylan.employee.model.EmployeeChangeAction;
import com.dylan.employee.model.EmployeeChangeRequest;
import com.dylan.employee.model.EmployeeChangeStatus;
import com.dylan.employee.model.Employee;
import com.dylan.employee.model.EmployeeWorkflowInboxMessage;
import com.dylan.employee.web.EmployeeChangeSubmitResponse;
import com.dylan.esquery.api.model.SourcePageResponse;
import com.dylan.workflow.web.WorkflowActionMessage;

/**
 * 员工业务服务，处理员工数据维护和索引源数据转换。
 */
@Service
public class EmployeeService {
	private static final int DEFAULT_PAGE_SIZE = 500;

	private final EmployeeMapper employeeMapper;
	private final EmployeeEmbeddingService embeddingService;
	private final EmployeeChangeEventPublisher changeEventPublisher;
	private final EmployeeChangeRequestRepository changeRequestRepository;
	private final EmployeeWorkflowInboxRepository inboxRepository;
	private final ApprovalGateway approvalGateway;
	private final int defaultEmbeddingDims;

	/**
	 * 创建 EmployeeService 实例并注入所需依赖。
	 */
	public EmployeeService(EmployeeMapper employeeMapper, EmployeeEmbeddingService embeddingService,
			EmployeeChangeEventPublisher changeEventPublisher, EmployeeChangeRequestRepository changeRequestRepository,
			EmployeeWorkflowInboxRepository inboxRepository, ApprovalGateway approvalGateway,
			@Value("${employee.embedding.dims:1024}") int defaultEmbeddingDims) {
		this.employeeMapper = employeeMapper;
		this.embeddingService = embeddingService;
		this.changeEventPublisher = changeEventPublisher;
		this.changeRequestRepository = changeRequestRepository;
		this.inboxRepository = inboxRepository;
		this.approvalGateway = approvalGateway;
		this.defaultEmbeddingDims = defaultEmbeddingDims;
	}

	/**
	 * 分页查询业务数据。
	 */
	public List<Employee> page(int page, int size) {
		int normalizedPage = Math.max(page, 1);
		int normalizedSize = normalizeSize(size);
		return employeeMapper.selectPage((normalizedPage - 1) * normalizedSize, normalizedSize);
	}

	/**
	 * 查询单条业务数据详情。
	 */
	public Employee detail(String idCardNo) {
		Employee employee = employeeMapper.selectByIdCardNo(idCardNo);
		if (employee == null) {
			throw new IllegalArgumentException("Employee not found: " + idCardNo);
		}
		return employee;
	}

	/**
	 * 统计业务数据数量。
	 */
	public long count() {
		return employeeMapper.countAll();
	}

	/**
	 * 创建业务对象。
	 */
	public EmployeeChangeSubmitResponse create(Map<String, Object> employee, String operator) {
		EmployeeChangeRequest request = newChangeRequest(EmployeeChangeAction.CREATE,
				String.valueOf(employee.get("idCardNo")), employee, operator);
		String processId = approvalGateway.submit(request);
		request.setApprovalProcessId(processId);
		changeRequestRepository.save(request);
		applyImmediatelyIfNoApproval(request, processId);
		return new EmployeeChangeSubmitResponse(request.getChangeRequestId(), processId);
	}

	/**
	 * 执行领域数据更新（字段级合并语义）。
	 * <p>
	 * Agent 可能只提交 {position: "HRBP"} 这样的稀疏对象。本方法先读取完整 employee，再将变更中非 null
	 * 字段覆盖到现有数据上，最后写入合并结果。 这确保 Agent 不会意外将其他列写成 null。
	 */
	public EmployeeChangeSubmitResponse update(String idCardNo, Map<String, Object> submitted, String operator) {
		EmployeeChangeRequest request = newChangeRequest(EmployeeChangeAction.UPDATE, idCardNo, submitted, operator);
		String processId = approvalGateway.submit(request);
		request.setApprovalProcessId(processId);
		changeRequestRepository.save(request);
		applyImmediatelyIfNoApproval(request, processId);
		return new EmployeeChangeSubmitResponse(request.getChangeRequestId(), processId);
	}

	public EmployeeChangeRequest changeRequestDetail(String changeRequestId) {
		return changeRequestRepository.findById(changeRequestId);
	}

	/**
	 * 先把工作流动作事件写入 Inbox，Kafka 消费线程只负责可靠接收。
	 */
	public void acceptWorkflowAction(WorkflowActionMessage message) {
		inboxRepository.saveIfAbsent(message);
	}

	/**
	 * 从 Inbox 重放工作流动作事件，审批通过后再应用员工变更。
	 */
	public void processWorkflowInboxMessage(EmployeeWorkflowInboxMessage inboxMessage) {
		String eventId = inboxMessage.getEventId();
		if (!inboxRepository.markProcessing(eventId)) {
			return;
		}
		WorkflowActionMessage message = inboxMessage.getMessage();
		if (!"employee.change.approved".equals(message.getActionName())) {
			inboxRepository.markProcessed(eventId);
			return;
		}
		try {
			String changeRequestId = changeRequestIdOf(message.getPayload());
			EmployeeChangeRequest request = changeRequestRepository.findById(changeRequestId);
			applyChange(request);
			inboxRepository.markProcessed(eventId);
		} catch (RuntimeException e) {
			inboxRepository.markFailed(eventId, e);
			throw e;
		}
	}

	private EmployeeChangeRequest newChangeRequest(EmployeeChangeAction action, String idCardNo,
			Map<String, Object> employee, String operator) {
		EmployeeChangeRequest request = new EmployeeChangeRequest();
		request.setChangeRequestId(UUID.randomUUID().toString());
		request.setAction(action);
		request.setStatus(EmployeeChangeStatus.PENDING_APPROVAL);
		request.setIdCardNo(idCardNo);
		request.setEmployee(employee);
		request.setApplicant(hasText(operator) ? operator : "system");
		return request;
	}

	private void applyImmediatelyIfNoApproval(EmployeeChangeRequest request, String processId) {
		if ("NO_APPROVAL".equals(processId)) {
			applyChange(request);
		}
	}

	private void applyChange(EmployeeChangeRequest request) {
		if (request.getStatus() == EmployeeChangeStatus.APPLIED) {
			return;
		}
		if (request.getAction() == EmployeeChangeAction.CREATE) {
			applyCreate(request.getEmployee());
		} else {
			applyUpdate(request.getIdCardNo(), request.getEmployee());
		}
		request.setStatus(EmployeeChangeStatus.APPLIED);
		changeRequestRepository.updateStatus(request.getChangeRequestId(), EmployeeChangeStatus.APPLIED);
	}

	private void applyCreate(Map<String, Object> employee) {
		employeeMapper.insert(employee);
		changeEventPublisher.publishUpsert(String.valueOf(employee.get("idCardNo")));
	}

	private void applyUpdate(String idCardNo, Map<String, Object> employee) {
		employee.put("idCardNo", idCardNo);
		int updated = employeeMapper.updateByIdCardNo(employee);
		if (updated == 0) {
			throw new IllegalArgumentException("Employee not found: " + idCardNo);
		}
		changeEventPublisher.publishUpsert(idCardNo);
	}

	private String changeRequestIdOf(Object payload) {
		if (payload instanceof Map<?, ?> payloadMap) {
			Object value = payloadMap.get("changeRequestId");
			if (value != null) {
				return String.valueOf(value);
			}
		}
		throw new IllegalArgumentException("Workflow action payload missing changeRequestId");
	}

	/**
	 * 删除业务数据。
	 */
	public void delete(String idCardNo) {
		int deleted = employeeMapper.deleteByIdCardNo(idCardNo);
		if (deleted == 0) {
			throw new IllegalArgumentException("Employee not found: " + idCardNo);
		}
		changeEventPublisher.publishDelete(idCardNo);
	}

	/**
	 * 提供索引源数据分页。
	 */
	public SourcePageResponse sourcePage(String since, String cursor, Integer batchSize, String embeddingField,
			Integer embeddingDims) {
		int offset = parseOffset(cursor);
		int size = normalizeSize(batchSize == null ? DEFAULT_PAGE_SIZE : batchSize);
		List<Employee> employees = employeeMapper.selectSourcePage(since, offset, size);
		long total = employeeMapper.countSource(since);

		SourcePageResponse response = new SourcePageResponse();
		response.setDocuments(toEsDocuments(employees, embeddingField, embeddingDims));
		response.setHasMore(offset + employees.size() < total);
		response.setNextCursor(String.valueOf(offset + employees.size()));
		return response;
	}

	/**
	 * 转换为目标请求或数据结构。
	 */
	public List<Map<String, Object>> toEsDocuments(List<Employee> employees) {
		return toEsDocuments(employees, null, null);
	}

	/**
	 * 转换为目标请求或数据结构。
	 */
	public List<Map<String, Object>> toEsDocuments(List<Employee> employees, String embeddingField,
			Integer embeddingDims) {
		List<Map<String, Object>> documents = new ArrayList<>();
		if (employees == null) {
			return documents;
		}
		for (Employee employee : employees) {
			documents.add(toEsDocument(employee, embeddingField, embeddingDims));
		}
		return documents;
	}

	/**
	 * 转换为目标请求或数据结构。
	 */
	public Map<String, Object> toEsDocument(Employee employee) {
		return toEsDocument(employee, null, null);
	}

	/**
	 * 转换为目标请求或数据结构。
	 */
	public Map<String, Object> toEsDocument(Employee employee, String embeddingField, Integer embeddingDims) {
		int safeEmbeddingDims = normalizeEmbeddingDims(embeddingDims);
		String embeddingText = buildEmbeddingText(employee);
		Map<String, Object> document = new HashMap<>();
		document.put("idCardNo", employee.getIdCardNo());
		document.put("chineseName", employee.getChineseName());
		document.put("contactAddress", employee.getContactAddress());
		document.put("memberNo", employee.getMemberNo());
		document.put("phoneNo", employee.getPhoneNo());
		document.put("email", employee.getEmail());
		document.put("position", employee.getPosition());
		document.put("operTime", employee.getOperTime());
		document.put("embeddingText", embeddingText);
		if (hasText(embeddingField)) {
			document.put(embeddingField, embeddingService.embed(embeddingText, safeEmbeddingDims));
		}
		return document;
	}

	/**
	 * 解析外部响应数据。
	 */
	private int parseOffset(String cursor) {
		if (cursor == null || cursor.isBlank()) {
			return 0;
		}
		return Integer.parseInt(cursor);
	}

	/**
	 * 规范化输入值。
	 */
	private int normalizeSize(int size) {
		if (size <= 0) {
			return DEFAULT_PAGE_SIZE;
		}
		return Math.min(size, 1000);
	}

	/**
	 * 构建请求或领域对象。
	 */
	private String buildEmbeddingText(Employee employee) {
		return String.join(" ", safe(employee.getChineseName()), safe(employee.getContactAddress()),
				safe(employee.getPosition()), safe(employee.getEducation()), safe(employee.getInstitution()),
				safe(employee.getMajor()), safe(employee.getWorkBaseSi()), safe(employee.getWorkBaseAf()));
	}

	/**
	 * 处理 safe 相关逻辑。
	 */
	private String safe(String value) {
		return value == null ? "" : value;
	}

	/**
	 * 规范化输入值。
	 */
	private int normalizeEmbeddingDims(Integer embeddingDims) {
		if (embeddingDims == null || embeddingDims <= 0) {
			return defaultEmbeddingDims;
		}
		return embeddingDims;
	}

	/**
	 * 判断是否存在指定条件。
	 */
	private boolean hasText(String value) {
		return value != null && !value.isBlank();
	}
}
