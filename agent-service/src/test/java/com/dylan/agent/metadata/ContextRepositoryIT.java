package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

import com.dylan.agent.metadata.context.internal.ContextRepository;

class ContextRepositoryIT {
    @Test
    void defaultFindCurrentIsEmptyForAbsentRecord() {
        ContextRepository repository = new NoopContextRepository();

        assertThat(repository.findCurrent(null, MetadataTestSupport.NOW)).isEmpty();
    }
}
