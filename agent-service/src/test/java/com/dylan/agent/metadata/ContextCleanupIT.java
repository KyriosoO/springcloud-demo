package com.dylan.agent.metadata;

import org.junit.jupiter.api.Test;

class ContextCleanupIT {
    @Test
    void cleanupJobSeamExists() {
        org.assertj.core.api.Assertions.assertThat(
                com.dylan.agent.metadata.context.internal.ContextCleanupJob.class)
                .isNotNull();
    }
}
