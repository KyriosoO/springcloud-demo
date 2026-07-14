package com.dylan.agent.adapter.api.document.provider;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
public record DocumentProviderWireError(String wireContractVersion,String operationId,CapabilityOperationType operationType,String requestDigest,DocumentProviderAdapterFailureCode failureCode,String diagnosticId) {
    public DocumentProviderWireError {
        if(!"DPW-1".equals(wireContractVersion)||operationType==null||failureCode==null)
            throw new IllegalArgumentException("document provider wire error incomplete");
        DocumentProviderContractValidation.text(operationId,"operationId");
        DocumentProviderContractValidation.digest(requestDigest,"requestDigest");
        if(diagnosticId==null||!diagnosticId.matches("[A-Za-z0-9._:-]{8,128}"))
            throw new IllegalArgumentException("diagnosticId is invalid");
    }
}
