package com.dylan.agent.metadata.domain.port;

import com.dylan.agent.adapter.api.AdapterRole;

import java.util.Objects;

/** 请求级 availability/currentness 复检使用的受控 role/domain key。 */
public record DomainAdapterKey(AdapterRole role, String domain) implements Comparable<DomainAdapterKey> {

    public DomainAdapterKey {
        Objects.requireNonNull(role, "role must not be null");
        Objects.requireNonNull(domain, "domain must not be null");
        domain = domain.trim();
        if (!domain.matches("[a-z][a-z0-9_]*")) {
            throw new IllegalArgumentException("domain must be lower snake case");
        }
    }

    @Override
    public int compareTo(DomainAdapterKey other) {
        int roleOrder = role.value().compareTo(other.role.value());
        return roleOrder != 0 ? roleOrder : domain.compareTo(other.domain);
    }
}
