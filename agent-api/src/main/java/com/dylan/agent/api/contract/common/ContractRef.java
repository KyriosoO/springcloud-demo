package com.dylan.agent.api.contract.common;

import java.util.Objects;

/**
 * Java 内部 schema/version 引用。
 *
 * <p>这是 kernel registration、context 声明和 result payload 契约共同使用的唯一
 * Java 值对象。它不是 URL、Java 类名或隐式 latest 选择器。
 */
public record ContractRef(String schema, String version) {

    public ContractRef {
        Objects.requireNonNull(schema, "schema must not be null");
        Objects.requireNonNull(version, "version must not be null");
        if (schema.isBlank()) {
            throw new IllegalArgumentException("schema must not be blank");
        }
        if (version.isBlank()) {
            throw new IllegalArgumentException("version must not be blank");
        }
        if (schema.contains("/") || schema.contains("#") || schema.contains(".")) {
            throw new IllegalArgumentException(
                    "ContractRef.schema must be a logical schema name: " + schema);
        }
        if ("latest".equalsIgnoreCase(version)) {
            throw new IllegalArgumentException("ContractRef.version must be explicit");
        }
    }
}
