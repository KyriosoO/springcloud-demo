package com.dylan.agent.kernel.binding;

import java.util.Objects;

/**
 * Metadata 边界按 Adapter Role + authorized domain + 当前可用性
 * 一次解析的请求级不可变 Adapter port 绑定。
 */
public final class AdapterExecutionBinding {

    private final String adapterRole;
    private final String domain;
    private final Object domainMode; // AgentDomainMode after D01 activation
    private final Object adapterPort;

    public AdapterExecutionBinding(String adapterRole, String domain,
                                    Object domainMode, Object adapterPort) {
        this.adapterRole = Objects.requireNonNull(adapterRole);
        this.domain = Objects.requireNonNull(domain);
        this.domainMode = Objects.requireNonNull(domainMode);
        this.adapterPort = Objects.requireNonNull(adapterPort);
    }

    public String adapterRole() { return adapterRole; }
    public String domain() { return domain; }
    public Object domainMode() { return domainMode; }
    public Object adapterPort() { return adapterPort; }
}
