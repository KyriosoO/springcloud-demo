package com.dylan.mqprocedureserver.service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import com.dylan.mqprocedureserver.mapper.TransactionMapper;
import com.dylan.transaction.api.model.AggregateRequest;
import com.dylan.transaction.api.model.Transaction;

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

	@Autowired
	private TransactionMapper transactionMapper;

	public List<Transaction> query(Transaction condition) {
		return transactionMapper.query(condition);
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
		// 分组列
		for (String field : validGroupBy) {
			if (!selectClause.isEmpty()) selectClause.append(", ");
			selectClause.append(FIELD_MAP.get(field)).append(" as ").append(field);
		}
		// 始终包含 count(*)
		if (!selectClause.isEmpty()) selectClause.append(", ");
		selectClause.append("count(*) as count");
		// 聚合指标
		for (MetricSpec ms : validMetrics) {
			selectClause.append(", ").append(ms.op).append("(")
					.append(FIELD_MAP.get(ms.field)).append(") as ")
					.append(ms.alias());
		}

		// 4. 构建 GROUP BY 子句
		String groupByClause = null;
		if (hasValidGroupBy) {
			groupByClause = validGroupBy.stream()
					.map(FIELD_MAP::get)
					.reduce((a, b) -> a + ", " + b)
					.orElse(null);
		}

		// 5. 构建结果
		Map<String, Object> result = new LinkedHashMap<>();

		if (hasValidGroupBy) {
			List<Map<String, Object>> groups = transactionMapper.aggregateDynamic(
					condition, selectClause.toString(), groupByClause);
			result.put("groups", groups);
		} else {
			// 无分组 → 全局聚合
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

		// 附加全局统计
		Map<String, Object> globalStats = transactionMapper.aggregate(
				condition != null ? condition : new Transaction());
		result.put("totalCount", globalStats.get("totalCount"));
		result.put("totalAmount", globalStats.get("totalAmount"));
		result.put("avgAmount", globalStats.get("avgAmount"));
		result.put("minAmount", globalStats.get("minAmount"));
		result.put("maxAmount", globalStats.get("maxAmount"));

		// 错误反馈
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

	/** Internal holder for parsed+validated metric spec. */
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
		return transactionMapper.findByTransId(transId);
	}

	public int delete(String transId) {
		return transactionMapper.deleteByTransId(transId);
	}
}
