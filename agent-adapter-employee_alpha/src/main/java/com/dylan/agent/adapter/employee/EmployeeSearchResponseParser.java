package com.dylan.agent.adapter.employee;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.AdapterAggregateResult;
import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.AggregateOrderAndLimitHelper;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateMetric;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * 解析下游 EmployeeSearch API 响应，包装为 AdapterQueryResult。
 * 处理分页信息、精确/非精确总数（relation: eq/gte）校验，以及 _source 字段的类型转换。
 */
@Component
public class EmployeeSearchResponseParser {

    private final ObjectMapper objectMapper;

    public EmployeeSearchResponseParser(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    /** 解析下游 EmployeeSearch API 响应，包装为 AdapterQueryResult。处理分页和精确/非精确总数。 */
    public AdapterQueryResult parse(String responseBody, int page, int size, int maxResponseBytes) {
        if (responseBody == null) {
            throw new AgentAdapterException("Employee 搜索响应为空。");
        }
        byte[] bytes = responseBody.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        if (bytes.length > maxResponseBytes) {
            throw new AgentAdapterException("Employee 搜索响应超过大小上限。");
        }

        JsonNode root = readRoot(bytes, "Employee 搜索响应 JSON 解析失败。");

        JsonNode hits = root.get("hits");
        if (hits == null) {
            throw new AgentAdapterException("Employee 搜索响应缺少 hits 字段。");
        }

        TotalHits totalHits = extractTotal(hits);
        List<Map<String, Object>> rows = extractSources(hits);

        if (rows.size() > size) {
            throw new AgentAdapterException("Employee 返回行数超出请求 size，下游契约异常。");
        }

        return new AdapterQueryResult(rows, totalHits.value(), totalHits.exact(), page, size);
    }

    /** 解析下游 EmployeeSearch 聚合响应，展平 ES nested buckets 为 AdapterAggregateResult。 */
    public AdapterAggregateResult parseAggregate(
            String responseBody,
            ValidatedAggregateQuery query,
            int maxResponseBytes) {
        if (responseBody == null) {
            throw new AgentAdapterException("Employee 聚合响应为空。");
        }
        byte[] bytes = responseBody.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        if (bytes.length > maxResponseBytes) {
            throw new AgentAdapterException("Employee 聚合响应超过大小上限。");
        }

        JsonNode root = readRoot(bytes, "Employee 聚合响应 JSON 解析失败。");
        JsonNode aggregations = root.get("aggregations");
        if (aggregations == null || !aggregations.isObject()) {
            throw new AgentAdapterException("Employee 聚合响应缺少 aggregations 字段。");
        }

        List<Map<String, Object>> rows = new ArrayList<>();
        collectRows(aggregations, query, 0, new LinkedHashMap<>(), rows);
        List<Map<String, Object>> ordered = AggregateOrderAndLimitHelper.orderAndLimit(rows, query);
        return new AdapterAggregateResult(ordered, rows.size() > ordered.size());
    }

    private JsonNode readRoot(byte[] bytes, String message) {
        try {
            return objectMapper.readTree(bytes);
        } catch (IOException e) {
            throw new AgentAdapterException(message, e);
        }
    }

    private TotalHits extractTotal(JsonNode hits) {
        JsonNode totalNode = hits.get("total");
        if (totalNode == null) {
            throw new AgentAdapterException("Employee 搜索响应缺少 total 字段。");
        }
        if (totalNode.isObject()) {
            JsonNode relation = totalNode.get("relation");
            boolean exact = true;
            if (relation != null) {
                if ("eq".equals(relation.asText())) {
                    exact = true;
                } else if ("gte".equals(relation.asText())) {
                    exact = false;
                } else {
                    throw new AgentAdapterException("Employee 搜索 total relation 非法。");
                }
            }
            JsonNode value = totalNode.get("value");
            if (value == null || !value.isIntegralNumber()) {
                throw new AgentAdapterException("Employee 搜索 total value 非法。");
            }
            long v = value.asLong();
            if (v < 0) throw new AgentAdapterException("Employee 搜索 total 为负数。");
            return new TotalHits(v, exact);
        }
        if (totalNode.isNumber()) {
            long v = totalNode.asLong();
            if (v < 0) throw new AgentAdapterException("Employee 搜索 total 为负数。");
            return new TotalHits(v, true);
        }
        throw new AgentAdapterException("Employee 搜索 total 格式不支持。");
    }

    private record TotalHits(long value, boolean exact) {}

    private void collectRows(JsonNode node, ValidatedAggregateQuery query, int groupIndex,
                             Map<String, Object> groups, List<Map<String, Object>> rows) {
        if (groupIndex >= query.getGroupByFields().size()) {
            Map<String, Object> row = new LinkedHashMap<>(groups);
            for (ValidatedAggregateMetric metric : query.getMetrics()) {
                row.put(metric.getAlias(), metricValue(node, metric));
            }
            rows.add(row);
            return;
        }

        String groupField = query.getGroupByFields().get(groupIndex);
        String aggregationName = "group_by_" + groupIndex + "_" + groupField;
        JsonNode groupAggregation = node.get(aggregationName);
        if (groupAggregation == null || !groupAggregation.isObject()) {
            throw new AgentAdapterException("Employee 聚合响应缺少分组: " + aggregationName);
        }
        JsonNode buckets = groupAggregation.get("buckets");
        if (buckets == null || !buckets.isArray()) {
            throw new AgentAdapterException("Employee 聚合响应分组 buckets 非法: " + aggregationName);
        }
        for (JsonNode bucket : buckets) {
            Map<String, Object> nextGroups = new LinkedHashMap<>(groups);
            nextGroups.put(groupField, scalar(bucket.get("key")));
            collectRows(bucket, query, groupIndex + 1, nextGroups, rows);
        }
    }

    private Object metricValue(JsonNode node, ValidatedAggregateMetric metric) {
        JsonNode metricNode = node.get(metric.getAlias());
        if (metricNode == null && "COUNT".equals(metric.getFunction().name())) {
            metricNode = node.get("doc_count");
        }
        if (metricNode == null) {
            throw new AgentAdapterException(
                    "Employee 聚合响应缺少 metric: " + metric.getAlias());
        }
        if (metricNode.isObject()) {
            return scalar(metricNode.get("value"));
        }
        return scalar(metricNode);
    }

    private Object scalar(JsonNode value) {
        if (value == null || value.isNull()) {
            return null;
        }
        if (value.isTextual()) {
            return value.asText();
        }
        if (value.isIntegralNumber()) {
            return value.longValue();
        }
        if (value.isFloatingPointNumber()) {
            return value.doubleValue();
        }
        if (value.isBoolean()) {
            return value.asBoolean();
        }
        return null;
    }

    private List<Map<String, Object>> extractSources(JsonNode hits) {
        JsonNode hitsArray = hits.get("hits");
        if (hitsArray == null || !hitsArray.isArray()) {
            throw new AgentAdapterException("Employee 搜索响应缺少 hits.hits 数组。");
        }
        List<Map<String, Object>> rows = new ArrayList<>();
        for (JsonNode hit : hitsArray) {
            JsonNode source = hit.get("_source");
            if (source == null || !source.isObject()) {
                continue;
            }
            Map<String, Object> row = new LinkedHashMap<>();
            var fields = source.fields();
            while (fields.hasNext()) {
                var entry = fields.next();
                JsonNode value = entry.getValue();
                if (value.isTextual()) {
                    row.put(entry.getKey(), value.asText());
                } else if (value.isNumber()) {
                    row.put(entry.getKey(), value.numberValue());
                } else if (value.isBoolean()) {
                    row.put(entry.getKey(), value.asBoolean());
                } else if (value.isNull()) {
                    row.put(entry.getKey(), null);
                }
            }
            rows.add(row);
        }
        return rows;
    }
}
