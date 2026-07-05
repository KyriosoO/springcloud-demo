package com.dylan.mqprocedureserver.service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.dylan.mqprocedureserver.config.TransactionSearchProperties;
import com.dylan.mqprocedureserver.mapper.TransactionMapper;
import com.dylan.transaction.api.model.AggregateRequest;
import com.dylan.transaction.api.model.Transaction;
import com.dylan.transaction.api.query.TransactionSearchRequest;
import com.dylan.transaction.api.query.TransactionSearchResponse;
import com.dylan.transaction.api.query.TransactionSearchSort;

@Service
public class TransactionService {

	private static final Logger log = LoggerFactory.getLogger(TransactionService.class);

	/** Transaction 模型字段 → DB 列名映射 */
	private static final Map<String, String> FIELD_MAP = Map.of(
			"transId", "TRANS_ID", "transType", "TRANS_TYPE",
			"transDate", "TRANS_DATE", "amount", "AMOUNT");
	/** 支持 MAX / MIN / SUM / AVG 的数值字段 */
	private static final Set<String> METRICABLE_FIELDS = Set.of("amount");
	/** 聚合运算白名单 */
	private static final Set<String> METRICS_OPS = Set.of("MAX", "MIN", "SUM", "AVG", "COUNT");

	private final TransactionMapper transactionMapper;
	private final TransactionSearchProperties searchProperties;

	public TransactionService(TransactionMapper transactionMapper,
							  TransactionSearchProperties searchProperties) {
		this.transactionMapper = transactionMapper;
		this.searchProperties = searchProperties;
	}

	public List<Transaction> query(Transaction condition) {
		return transactionMapper.query(condition, null, null, null);
	}

	public TransactionSearchResponse search(TransactionSearchRequest request) {
		validateSearchRequest(request);

		Transaction condition = request.getCondition();
		int page = request.getPage();
		int size = request.getSize();
		int offset = calculateOffset(page, size);
		int maxExactTotal = searchProperties.getMaxExactTotal();
		int countLimit = Math.addExact(maxExactTotal, 1);
		String orderByClause = buildOrderByClause(request.getSorts());

		long observed = transactionMapper.countUpTo(condition, countLimit);
		if (observed == 0) {
			TransactionSearchResponse resp = new TransactionSearchResponse();
			resp.setRows(List.of());
			resp.setTotal(0);
			resp.setTotalExact(true);
			resp.setPage(page);
			resp.setSize(size);
			return resp;
		}

		List<Transaction> rows = transactionMapper.query(condition, offset, size, orderByClause);

		long total = Math.min(observed, maxExactTotal);
		boolean totalExact = observed <= maxExactTotal;

		TransactionSearchResponse resp = new TransactionSearchResponse();
		resp.setRows(rows);
		resp.setTotal(total);
		resp.setTotalExact(totalExact);
		resp.setPage(page);
		resp.setSize(size);
		return resp;
	}

	String buildOrderByClause(List<TransactionSearchSort> sorts) {
		if (sorts == null || sorts.isEmpty()) {
			return null;
		}
		if (sorts.size() > 2) {
			throw new IllegalArgumentException("排序字段最多支持 2 个。");
		}
		List<String> clauses = new ArrayList<>();
		Set<String> seen = new java.util.LinkedHashSet<>();
		boolean containsTransId = false;
		for (TransactionSearchSort sort : sorts) {
			if (sort == null || sort.getField() == null || sort.getField().isBlank()) {
				throw new IllegalArgumentException("排序字段不能为空。");
			}
			String field = sort.getField().trim();
			String column = FIELD_MAP.get(field);
			if (column == null) {
				throw new IllegalArgumentException("不支持的排序字段：" + field);
			}
			if (!seen.add(field)) {
				throw new IllegalArgumentException("排序字段不能重复：" + field);
			}
			String direction = normalizeSortDirection(sort.getDirection());
			clauses.add(column + " " + direction);
			if ("transId".equals(field)) {
				containsTransId = true;
			}
		}
		if (!containsTransId) {
			clauses.add("TRANS_ID ASC");
		}
		return String.join(", ", clauses);
	}

	private String normalizeSortDirection(String direction) {
		if (direction == null || direction.isBlank()) {
			throw new IllegalArgumentException("排序方向不能为空。");
		}
		String normalized = direction.trim().toUpperCase(java.util.Locale.ROOT);
		if (!"ASC".equals(normalized) && !"DESC".equals(normalized)) {
			throw new IllegalArgumentException("排序方向只支持 ASC 或 DESC。");
		}
		return normalized;
	}

	private void validateSearchRequest(TransactionSearchRequest request) {
		if (request == null) {
			throw new IllegalArgumentException("搜索请求不能为空。");
		}
		if (request.getCondition() == null) {
			throw new IllegalArgumentException("搜索条件不能为空。");
		}
		if (!hasCondition(request.getCondition())) {
			throw new IllegalArgumentException("至少需要一个查询条件。");
		}
		if (request.getPage() < 1) {
			throw new IllegalArgumentException("page 必须 >= 1。");
		}
		if (request.getSize() < 1 || request.getSize() > 100) {
			throw new IllegalArgumentException("size 必须在 1～100 之间。");
		}
		if (searchProperties.getMaxExactTotal() <= 0) {
			throw new IllegalStateException("transaction.search.max-exact-total 必须为正数。");
		}
	}

	private boolean hasCondition(Transaction condition) {
		return (condition.getTransId() != null && !condition.getTransId().isBlank())
				|| (condition.getTransType() != null && !condition.getTransType().isBlank())
				|| (condition.getTransTypeContains() != null && !condition.getTransTypeContains().isBlank())
				|| condition.getTransDate() != null
				|| condition.getTransDateGt() != null
				|| condition.getTransDateLt() != null
				|| condition.getAmount() != null
				|| condition.getAmountGt() != null
				|| condition.getAmountLt() != null;
	}

	private int calculateOffset(int page, int size) {
		try {
			return Math.multiplyExact(page - 1, size);
		} catch (ArithmeticException e) {
			throw new IllegalArgumentException("分页偏移计算溢出。");
		}
	}

	/**
	 * 聚合统计 —— 支持任意 Transaction 字段组合分组 + COUNT/MAX/MIN/SUM/AVG。
	 *
	 * <pre>
	 *   groupBy:  字段名列表，须存在于 Transaction 模型
	 *   metrics:  "OPERATION:FIELD" 或 "COUNT"
	 *             示例: ["SUM:amount", "AVG:amount", "COUNT"]
	 * </pre>
	 */
	public Map<String, Object> aggregate(AggregateRequest request) {
		Transaction condition = request.getCondition();
		List<String> groupBy = request.getGroupBy();
		List<String> metrics = request.getMetrics();

		// 1. 校验 groupBy 字段
		List<String> validGroupBy = new ArrayList<>();
		List<String> invalidGroupBy = new ArrayList<>();
		if (groupBy != null) {
			for (String field : groupBy) {
				if (FIELD_MAP.containsKey(field)) {
					validGroupBy.add(field);
				} else {
					invalidGroupBy.add(field);
				}
			}
		}

		boolean hasValidGroupBy = !validGroupBy.isEmpty();

		// 2. 解析并校验 metrics
		List<MetricSpec> validMetrics = new ArrayList<>();
		List<String> invalidMetrics = new ArrayList<>();
		if (metrics != null) {
			for (String m : metrics) {
				if ("COUNT".equalsIgnoreCase(m)) {
					continue;
				}
				int colon = m.indexOf(':');
				if (colon <= 0 || colon == m.length() - 1) {
					invalidMetrics.add(m);
					continue;
				}
				String op = m.substring(0, colon).toUpperCase();
				String field = m.substring(colon + 1);
				if (!METRICS_OPS.contains(op)) {
					invalidMetrics.add(m + " (unsupported op: " + op + ")");
				} else if (!METRICABLE_FIELDS.contains(field)) {
					invalidMetrics.add(m + " (non-metricable field: " + field + "; only: " + METRICABLE_FIELDS + ")");
				} else {
					validMetrics.add(new MetricSpec(op, field));
				}
			}
		}

		// 3. 构建 SELECT 子句
		StringBuilder selectClause = new StringBuilder();
		for (String field : validGroupBy) {
			if (!selectClause.isEmpty()) selectClause.append(", ");
			selectClause.append(FIELD_MAP.get(field)).append(" as ").append(field);
		}
		if (!selectClause.isEmpty()) selectClause.append(", ");
		selectClause.append("count(*) as count");
		for (MetricSpec ms : validMetrics) {
			selectClause.append(", ").append(ms.op).append("(")
					.append(FIELD_MAP.get(ms.field)).append(") as ")
					.append(ms.alias());
		}

		String groupByClause = null;
		if (hasValidGroupBy) {
			groupByClause = validGroupBy.stream()
					.map(FIELD_MAP::get)
					.reduce((a, b) -> a + ", " + b)
					.orElse(null);
		}

		Map<String, Object> result = new LinkedHashMap<>();

		if (hasValidGroupBy) {
			List<Map<String, Object>> groups = transactionMapper.aggregateDynamic(
					condition, selectClause.toString(), groupByClause);
			result.put("groups", groups);
		} else {
			Map<String, Object> global = transactionMapper.aggregate(condition);
			List<Map<String, Object>> globalGroup = new ArrayList<>();
			Map<String, Object> row = new LinkedHashMap<>();
			row.put("count", global.get("totalCount"));
			for (MetricSpec ms : validMetrics) {
				String key = switch (ms.op) {
					case "SUM" -> "totalAmount";
					case "AVG" -> "avgAmount";
					case "MIN" -> "minAmount";
					case "MAX" -> "maxAmount";
					default -> ms.alias();
				};
				row.put(ms.alias(), global.get(key));
			}
			globalGroup.add(row);
			result.put("groups", globalGroup);
		}

		Map<String, Object> globalStats = transactionMapper.aggregate(
				condition != null ? condition : new Transaction());
		result.put("totalCount", globalStats.get("totalCount"));
		result.put("totalAmount", globalStats.get("totalAmount"));
		result.put("avgAmount", globalStats.get("avgAmount"));
		result.put("minAmount", globalStats.get("minAmount"));
		result.put("maxAmount", globalStats.get("maxAmount"));

		if (!invalidGroupBy.isEmpty()) {
			result.put("invalidGroupBy", invalidGroupBy);
			result.put("message", "Invalid groupBy fields: " + invalidGroupBy
					+ ". Valid fields: " + FIELD_MAP.keySet());
		}
		if (!invalidMetrics.isEmpty()) {
			result.put("invalidMetrics", invalidMetrics);
			String msg = result.containsKey("message")
					? result.get("message") + "; Invalid metrics: " + invalidMetrics
					: "Invalid metrics: " + invalidMetrics;
			result.put("message", msg);
		}

		return result;
	}

	private record MetricSpec(String op, String field) {
		String alias() {
			return op.toLowerCase() + field.substring(0, 1).toUpperCase() + field.substring(1);
		}
	}

	public Transaction create(Transaction transaction) {
		transactionMapper.insert(transaction);
		return transaction;
	}

	public Transaction getByTransId(String transId) {
		Transaction condition = new Transaction();
		condition.setTransId(transId);
		return transactionMapper.findByCondition(condition);
	}

	public Transaction findByCondition(Transaction condition) {
		return transactionMapper.findByCondition(condition);
	}

	public int delete(String transId) {
		return transactionMapper.deleteByTransId(transId);
	}

	public int update(Transaction transaction) {
		return transactionMapper.update(transaction);
	}
}
