package com.dylan.agent.kernel.binding;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.AgentAdapterPort;

import java.time.Instant;
import java.util.Objects;

/**
 * Metadata 边界按 Adapter Role + authorized domain + 当前可用性
 * 一次解析的请求级不可变 Adapter port 绑定。
 */
public final class AdapterExecutionBinding {

    private final AdapterRole adapterRole;
    private final String domain;
    private final Class<? extends AgentAdapterPort> portType;
    private final AgentAdapterPort port;
    private final String adapterRegistrationVersion;
    private final Instant resolvedAt;

    public AdapterExecutionBinding(AdapterRole adapterRole,
                                   String domain,
                                   Class<? extends AgentAdapterPort> portType,
                                   AgentAdapterPort port,
                                   String adapterRegistrationVersion,
                                   Instant resolvedAt) {
        this.adapterRole = Objects.requireNonNull(adapterRole);
        this.domain = Objects.requireNonNull(domain);
        this.portType = Objects.requireNonNull(portType);
        this.port = Objects.requireNonNull(port);
        this.adapterRegistrationVersion = Objects.requireNonNull(adapterRegistrationVersion);
        this.resolvedAt = Objects.requireNonNull(resolvedAt);
        if (!portType.isInstance(port)) {
            throw new IllegalArgumentException("port does not implement declared portType");
        }
    }

    public AdapterRole adapterRole() { return adapterRole; }
    public String domain() { return domain; }
    public Class<? extends AgentAdapterPort> portType() { return portType; }
    public AgentAdapterPort port() { return port; }
    public String adapterRegistrationVersion() { return adapterRegistrationVersion; }
    public Instant resolvedAt() { return resolvedAt; }
}
