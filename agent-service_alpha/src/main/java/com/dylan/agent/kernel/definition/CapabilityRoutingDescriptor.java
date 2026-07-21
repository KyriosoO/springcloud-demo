package com.dylan.agent.kernel.definition;

import java.util.List;
import java.util.Objects;

/**
 * Capability Routing Descriptor，Definition 内的静态能力路由事实。
 * 只保存通用语义，不写 domain 名称、字段、角色或权限。
 */
public final class CapabilityRoutingDescriptor {

    private final String modelDescription;
    private final List<String> applicability;
    private final List<String> exclusions;

    public CapabilityRoutingDescriptor(String modelDescription,
                                       List<String> applicability,
                                       List<String> exclusions) {
        this.modelDescription = Objects.requireNonNull(modelDescription);
        if (modelDescription.isBlank() || modelDescription.length() > 2000) {
            throw new IllegalArgumentException("modelDescription 1-2000 chars required");
        }
        this.applicability = List.copyOf(applicability != null ? applicability : List.of());
        this.exclusions = List.copyOf(exclusions != null ? exclusions : List.of());
    }

    public String modelDescription() { return modelDescription; }
    public List<String> applicability() { return applicability; }
    public List<String> exclusions() { return exclusions; }
}
