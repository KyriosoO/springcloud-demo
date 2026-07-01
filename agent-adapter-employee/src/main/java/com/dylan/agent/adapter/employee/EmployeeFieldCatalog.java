package com.dylan.agent.adapter.employee;

import java.util.Set;

/**
 * Employee 域字段目录，提供 supportedFields() 所用字段集合。
 * 与 AgentProperties 中配置的字段集合保持一致，作为权限校验的字段白名单。
 */
public final class EmployeeFieldCatalog {

    private static final Set<String> SUPPORTED = Set.of(
            "contactAddress", "chineseName", "idCardNo", "memberNo", "phoneNo", "email", "position");

    private EmployeeFieldCatalog() {}

    public static Set<String> supportedFields() {
        return SUPPORTED;
    }
}
