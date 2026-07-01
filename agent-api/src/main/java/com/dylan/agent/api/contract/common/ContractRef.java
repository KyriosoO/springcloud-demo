package com.dylan.agent.api.contract.common;

import java.util.Objects;

/**
 * Java internal schema/version reference.
 *
 * <p>This is the only Java value object used by kernel registration, context
 * declarations and result payload contracts. It is not a URL, Java class name
 * or implicit latest selector.
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
