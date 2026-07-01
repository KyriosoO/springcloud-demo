package com.dylan.agent.adapter.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;

class AdapterQueryResultTest {

    @Test
    void shouldDefensivelyCopyRowsAndMaps() {
        Map<String, Object> sourceRow = new LinkedHashMap<>();
        sourceRow.put("transId", "T001");
        sourceRow.put("transDate", null);
        List<Map<String, Object>> sourceRows = new ArrayList<>();
        sourceRows.add(sourceRow);

        AdapterQueryResult result = new AdapterQueryResult(sourceRows, 1, false, 1, 20);
        sourceRow.put("transId", "CHANGED");
        sourceRows.clear();

        assertThat(result.getRows()).hasSize(1);
        assertThat(result.getRows().getFirst())
                .containsEntry("transId", "T001")
                .containsEntry("transDate", null);
        assertThat(result.isTotalExact()).isFalse();
        assertThatThrownBy(() -> result.getRows().getFirst().put("x", "y"))
                .isInstanceOf(UnsupportedOperationException.class);
    }
}
