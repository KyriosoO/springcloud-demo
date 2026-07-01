package com.dylan.agent.api.capability;

import java.util.List;

import io.swagger.v3.oas.annotations.media.Schema;

/** Capability 上下文读写声明，描述能力执行时依赖和产出的上下文字段。 */
@Schema(description = "Capability 上下文读写声明")
public class CapabilityContextSpec {

    @Schema(description = "读取的上下文键，例如 previousQuery")
    private List<String> reads;

    @Schema(description = "写入的上下文键，例如 RuntimeQueryContext、RuntimeAggregateContext")
    private List<String> writes;

    public CapabilityContextSpec() {
    }

    public List<String> getReads() { return reads; }
    public void setReads(List<String> reads) { this.reads = reads; }
    public List<String> getWrites() { return writes; }
    public void setWrites(List<String> writes) { this.writes = writes; }
}
