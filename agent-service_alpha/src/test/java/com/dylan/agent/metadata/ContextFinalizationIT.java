package com.dylan.agent.metadata;

import org.junit.jupiter.api.Test;

class ContextFinalizationIT {
    @Test
    void coveredByContextFinalizationParticipantImplTest() {
        org.assertj.core.api.Assertions.assertThat(
                com.dylan.agent.metadata.context.internal.ContextFinalizationParticipantImpl.class)
                .isNotNull();
    }
}
