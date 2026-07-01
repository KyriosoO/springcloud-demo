package com.dylan.agent.kernel.definition;

import java.util.Objects;

/**
 * Java 内部 schema/version 唯一值对象。
 *
 * <p>禁止 URL、Java class name 和隐式 latest 语义。解析由 ContractRegistry 完成。
 */
public record ContractRef(String schema, String version) {

    public ContractRef {
        Objects.requireNonNull(schema);
        Objects.requireNonNull(version);
        if (schema.isBlank()) throw new IllegalArgumentException("schema must not be blank");
        if (version.isBlank()) throw new IllegalArgumentException("version must not be blank");
        if (schema.contains("/schemas/")) throw new IllegalArgumentException(
                "ContractRef.schema must not be a raw JSON Pointer; use logical name. Got: " + schema);
    }
}
