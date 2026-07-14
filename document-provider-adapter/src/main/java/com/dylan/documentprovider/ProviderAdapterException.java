package com.dylan.documentprovider;

import com.dylan.agent.adapter.api.document.provider.DocumentProviderAdapterFailureCode;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;

final class ProviderAdapterException extends RuntimeException {
    final String operationId;
    final CapabilityOperationType operationType;
    final String requestDigest;
    final DocumentProviderAdapterFailureCode code;
    final String diagnosticId;

    ProviderAdapterException(String operationId, CapabilityOperationType operationType, String requestDigest,
                             DocumentProviderAdapterFailureCode code, String diagnosticId) {
        super(code.name());
        this.operationId = operationId;
        this.operationType = operationType;
        this.requestDigest = requestDigest;
        this.code = code;
        this.diagnosticId = diagnosticId;
    }
}
