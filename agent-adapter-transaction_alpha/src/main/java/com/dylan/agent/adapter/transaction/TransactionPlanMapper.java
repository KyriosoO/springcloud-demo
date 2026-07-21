package com.dylan.agent.adapter.transaction;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.format.DateTimeParseException;
import java.util.Date;
import java.util.regex.Pattern;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateMetric;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.transaction.api.model.AggregateRequest;
import com.dylan.transaction.api.model.Transaction;
import com.dylan.transaction.api.query.TransactionSearchRequest;
import com.dylan.transaction.api.query.TransactionSearchSort;

/**
 * 将 ValidatedFilter 映射为下游 TransactionSearch API 所需的 filter 参数结构。
 * 处理 DECIMAL 类型的金额值解析和 INSTANT 类型的 UTC 时区转换，按字段分发 operator 语义。
 */
@Component
public class TransactionPlanMapper {

    private static final Pattern PLAIN_DECIMAL = Pattern.compile("[+-]?\\d+(?:\\.\\d+)?");

    /** 将 ValidatedFilter 列表映射为下游 TransactionSearch API 的请求参数。处理 DECIMAL/INSTANT 值转换。 */
    public TransactionSearchRequest toSearchRequest(ValidatedQuery query) {
        Transaction condition = new Transaction();
        for (ValidatedFilter filter : query.getFilters()) {
            applyFilter(condition, filter);
        }

        TransactionSearchRequest req = new TransactionSearchRequest();
        req.setCondition(condition);
        req.setPage(query.getPage());
        req.setSize(query.getSize());
        req.setSorts(query.getSorts().stream()
                .map(sort -> new TransactionSearchSort(sort.getField(), sort.getDirection()))
                .toList());
        return req;
    }

    /** 将聚合查询映射为下游 Transaction 聚合请求。 */
    public AggregateRequest toAggregateRequest(ValidatedAggregateQuery query) {
        Transaction condition = new Transaction();
        for (ValidatedFilter filter : query.getFilters()) {
            applyFilter(condition, filter);
        }
        return new AggregateRequest(condition, query.getGroupByFields(),
                query.getMetrics().stream()
                        .map(TransactionPlanMapper::metricExpression)
                        .toList());
    }

    void applyFilter(Transaction condition, ValidatedFilter filter) {
        String field = filter.getField();
        AgentOperator op = filter.getOperator();

        switch (field) {
            case "transId" -> {
                if (op == AgentOperator.EQ) condition.setTransId(filter.getValue());
                else throw unsupported(op, field);
            }
            case "transType" -> {
                switch (op) {
                    case EQ -> condition.setTransType(filter.getValue());
                    case CONTAINS -> condition.setTransTypeContains(filter.getValue());
                    default -> throw unsupported(op, field);
                }
            }
            case "transDate" -> {
                Date parsed = parseInstant(filter.getValue());
                switch (op) {
                    case GT -> condition.setTransDateGt(parsed);
                    case LT -> condition.setTransDateLt(parsed);
                    default -> throw unsupported(op, field);
                }
            }
            case "amount" -> {
                BigDecimal parsed = parseAmount(filter.getValue());
                switch (op) {
                    case EQ -> condition.setAmount(parsed);
                    case GT -> condition.setAmountGt(parsed);
                    case LT -> condition.setAmountLt(parsed);
                    default -> throw unsupported(op, field);
                }
            }
            default -> throw new AgentAdapterException("Transaction 不支持字段: " + field);
        }
    }

    static String metricExpression(ValidatedAggregateMetric metric) {
        if (metric.getFunction() == AggregateFunction.COUNT) {
            return "COUNT";
        }
        return metric.getFunction().name() + ":" + metric.getField();
    }

    static String downstreamMetricAlias(ValidatedAggregateMetric metric) {
        if (metric.getFunction() == AggregateFunction.COUNT) {
            return "count";
        }
        String field = metric.getField();
        return metric.getFunction().name().toLowerCase()
                + field.substring(0, 1).toUpperCase()
                + field.substring(1);
    }

    private static AgentAdapterException unsupported(AgentOperator op, String field) {
        return new AgentAdapterException("Transaction 域不支持 operator: " + op + " on " + field);
    }

    /** 解析金额字符串为下游 API 所需的 Decimal 类型。 */
    static BigDecimal parseAmount(String value) {
        String normalized = value == null ? "" : value.trim();
        if (!PLAIN_DECIMAL.matcher(normalized).matches()) {
            throw new AgentAdapterException("无效的规范化金额值: " + value);
        }
        try {
            return new BigDecimal(normalized);
        } catch (NumberFormatException e) {
            throw new AgentAdapterException("无效的规范化金额值: " + value, e);
        }
    }

    /** 解析 ISO-8601 时间字符串，去除时区后缀（下游 API 要求）。 */
    static Date parseInstant(String value) {
        String normalized = value == null ? "" : value.trim();
        try {
            Instant instant = Instant.parse(normalized);
            if (instant.getNano() != 0 || !instant.toString().equals(normalized)) {
                throw new AgentAdapterException("无效的规范化 UTC 时间: " + value);
            }
            return Date.from(instant);
        } catch (DateTimeParseException e) {
            throw new AgentAdapterException("无效的规范化 UTC 时间: " + value, e);
        }
    }
}
