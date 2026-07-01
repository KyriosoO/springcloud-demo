package com.dylan.agent.result;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.response.AgentQueryResult;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.model.FieldPolicy;
import com.dylan.agent.mask.FieldMaskerRegistry;
import com.dylan.agent.security.AgentPermissionService;

/**
 * 统一结果处理器。
 * 顺序: selectFields → display 权限 → mask → 构造安全响应。
 */
@Component
public class AgentResultProcessor {

    private final AgentPermissionService permissionService;
    private final FieldMaskerRegistry maskerRegistry;

    public AgentResultProcessor(AgentPermissionService permissionService, FieldMaskerRegistry maskerRegistry) {
        this.permissionService = permissionService;
        this.maskerRegistry = maskerRegistry;
    }

    /** 处理查询结果：按 selectFields + display 权限 + mask 规则逐列过滤脱敏，构造安全响应。 */
    public AgentQueryResult process(AdapterQueryResult rawResult, ValidatedQuery query,
                                    AgentUserContext userContext, String domain) {
        List<String> columns = query.getSelectFields();
        List<Map<String, Object>> rows = rawResult.getRows().stream()
                .map(row -> processRow(row, columns, userContext, domain))
                .toList();

        AgentQueryResult result = new AgentQueryResult();
        result.setColumns(columns);
        result.setRows(rows);
        result.setTotal(rawResult.getTotal());
        result.setTotalExact(rawResult.isTotalExact());
        result.setPage(rawResult.getPage());
        result.setSize(rawResult.getSize());
        return result;
    }

    private Map<String, Object> processRow(Map<String, Object> row, List<String> selectFields,
                                           AgentUserContext context, String domain) {
        Map<String, Object> safe = new LinkedHashMap<>();
        for (String field : selectFields) {
            Object value = row.get(field);
            // 再次校验 display 权限
            FieldPolicy policy = permissionService.getDisplayPolicy(context, domain, field);
            if (context.getRoles().stream().noneMatch(r -> policy.getDisplayRoles().contains(r))) {
                continue; // 跳过未授权字段
            }
            Object sanitized = sanitizeScalar(value);
            Object masked = maskerRegistry.mask(policy.getMaskType(), sanitized);
            safe.put(field, masked);
        }
        return safe;
    }

    private Object sanitizeScalar(Object value) {
        if (value == null) return null;
        if (value instanceof String || value instanceof Number || value instanceof Boolean) {
            return value;
        }
        // 拒绝 Object/Array 进入结果
        return null;
    }
}
