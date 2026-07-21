package com.dylan.agent.adapter.employee;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * Employee 域适配器配置属性，从 {@code agent.adapters.employee} 前缀的 YAML 加载。
 * 控制下游响应的大小上限，防止 OOM。
 */
@Component
@ConfigurationProperties(prefix = "agent.adapters.employee")
public class EmployeeAdapterProperties {

    private int maxResponseBytes = 2_097_152;

    public int getMaxResponseBytes() { return maxResponseBytes; }
    public void setMaxResponseBytes(int maxResponseBytes) { this.maxResponseBytes = maxResponseBytes; }
}
