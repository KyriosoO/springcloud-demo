package com.dylan.agent.application;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Files;
import java.nio.file.Path;

import org.junit.jupiter.api.Test;

class AgentHtmlContractTest {

    @Test
    void rendersTypedQueryPreviewResultWithoutLegacyTopLevelFields() throws Exception {
        String html = Files.readString(Path.of("src/main/resources/static/agent.html"));

        assertThat(html).contains("QUERY_PREVIEW");
        assertThat(html).contains("renderQueryPreviewResult(result.previewResult)");
        assertThat(html).doesNotContain("data.queryResult");
        assertThat(html).doesNotContain("data.aggregateResult");
        assertThat(html).doesNotContain("data.intent");
        assertThat(html).doesNotContain("data.plan");
    }
}
