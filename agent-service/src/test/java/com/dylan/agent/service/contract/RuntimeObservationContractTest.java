package com.dylan.agent.service.contract;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;

class RuntimeObservationContractTest {
    @Test
    void rejectsDuplicateSequencesAndInconsistentTerminalFields() {
        RuntimeObservation.ModelCall model = new RuntimeObservation.ModelCall(
                1, "business_query_plan", "v1", Map.of("input", Map.of()),
                "succeeded", null);
        RuntimeObservation.Plan plan = new RuntimeObservation.Plan(
                1, "business_query_plan", "llm", "accepted", Map.of("action", "employee.search"));

        assertThatThrownBy(() -> new RuntimeInspectResponse(
                1, "req", CapabilityStatus.SUCCESS, "employee.search", null, Map.of(), null,
                List.of(model), List.of(plan), List.of()))
                .isInstanceOf(IllegalArgumentException.class);

        assertThatThrownBy(() -> new RuntimeObservation.DownstreamCall(
                2, "employee-service", "employee.search", "POST", "/employees/es/search",
                Map.of(), "completed", null, 1L))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
