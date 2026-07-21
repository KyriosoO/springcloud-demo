package com.dylan.agent.api.contract.common;

import java.util.Objects;

/**
 * Java 内部 namespace/name/version 引用。
 *
 * <p>这是 kernel registration、context 声明和 result payload 契约共同使用的唯一
 * Java 值对象。它不是 URL、Java 类名或隐式 latest 选择器。
 */
public record ContractRef(String namespace, String name, String version) {

    public ContractRef {
        Objects.requireNonNull(namespace, "namespace must not be null");
        Objects.requireNonNull(name, "name must not be null");
        Objects.requireNonNull(version, "version must not be null");
        if (!namespace.matches("[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*")) {
            throw new IllegalArgumentException("ContractRef.namespace is invalid: " + namespace);
        }
        if (!name.matches("[A-Za-z][A-Za-z0-9_]*")) {
            throw new IllegalArgumentException(
                    "ContractRef.name must be a logical contract name: " + name);
        }
        if (version.isBlank()) {
            throw new IllegalArgumentException("version must not be blank");
        }
        if ("latest".equalsIgnoreCase(version)) {
            throw new IllegalArgumentException("ContractRef.version must be explicit");
        }
    }
}
