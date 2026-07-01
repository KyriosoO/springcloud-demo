package com.dylan.agent.api.enums;

import io.swagger.v3.oas.annotations.media.Schema;

/** Agent RESULT payload discriminator. */
@Schema(description = "Agent RESULT payload kind")
public enum AgentResultKind {
    @Schema(description = "Query result payload")
    QUERY,
    @Schema(description = "Aggregate result payload")
    AGGREGATE
}
