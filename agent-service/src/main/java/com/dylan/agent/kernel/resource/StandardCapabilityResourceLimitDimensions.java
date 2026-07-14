package com.dylan.agent.kernel.resource;

import java.util.Set;

/** 表格型 Capability 资源契约的稳定维度。 */
public final class StandardCapabilityResourceLimitDimensions {

    public static final ResourceLimitDimension PAGE_SIZE = new ResourceLimitDimension("page.size");
    public static final ResourceLimitDimension RESULT_ROWS = new ResourceLimitDimension("result.rows");
    public static final ResourceLimitDimension RESULT_BYTES = new ResourceLimitDimension("result.bytes");
    public static final Set<ResourceLimitDimension> ALL = Set.of(PAGE_SIZE, RESULT_ROWS, RESULT_BYTES);

    private StandardCapabilityResourceLimitDimensions() {
    }
}
