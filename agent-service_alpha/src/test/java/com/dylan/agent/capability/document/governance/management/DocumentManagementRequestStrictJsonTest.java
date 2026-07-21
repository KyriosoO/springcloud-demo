package com.dylan.agent.capability.document.governance.management;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentManagementRequestStrictJsonTest {
    @Test void rejectsUnknownManagementField(){
        ObjectMapper mapper=new ObjectMapper().findAndRegisterModules();
        assertThatThrownBy(()->mapper.readValue("{\"idempotencyKey\":\"change-key\",\"deadline\":\"2026-07-14T09:00:00Z\",\"approval\":true}",DocumentReconcileRequest.class))
                .hasRootCauseInstanceOf(IllegalArgumentException.class);
    }
}
