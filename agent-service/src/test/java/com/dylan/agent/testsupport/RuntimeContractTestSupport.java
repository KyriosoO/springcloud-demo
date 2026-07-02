package com.dylan.agent.testsupport;

import com.dylan.agent.api.contract.runtime.common.RuntimeOperationMetadata;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.api.contract.runtime.common.RuntimeTerminationReason;

public final class RuntimeContractTestSupport {

    private RuntimeContractTestSupport() {
    }

    public static RuntimeOperationMetadata metadata(RuntimeOperationType operation) {
        RuntimeOperationMetadata metadata = new RuntimeOperationMetadata();
        metadata.setOperation(operation);
        metadata.setProviderAttempts(1);
        metadata.setRepairAttempts(0);
        metadata.setRepairDurationMs(0L);
        metadata.setTotalDurationMs(1L);
        metadata.setTerminationReason(RuntimeTerminationReason.COMPLETED);
        metadata.setDeadlineReached(false);
        metadata.setRepairLimitReached(false);
        return metadata;
    }
}
