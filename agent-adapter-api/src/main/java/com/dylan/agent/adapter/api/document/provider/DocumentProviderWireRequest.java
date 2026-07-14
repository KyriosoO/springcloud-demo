package com.dylan.agent.adapter.api.document.provider;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
public record DocumentProviderWireRequest<T>(String wireContractVersion,String operationId,CapabilityOperationType operationType,String requestDigest,long absoluteDeadlineEpochMillis,String expectedActivationDigest,String expectedProviderBindingDigest,T input) {
    public DocumentProviderWireRequest {
        if(!"DPW-1".equals(wireContractVersion)||operationType==null||input==null||absoluteDeadlineEpochMillis<=0)
            throw new IllegalArgumentException("document provider wire request incomplete");
        DocumentProviderContractValidation.text(operationId,"operationId");
        DocumentProviderContractValidation.digest(requestDigest,"requestDigest");
        DocumentProviderContractValidation.digest(expectedActivationDigest,"expectedActivationDigest");
        DocumentProviderContractValidation.digest(expectedProviderBindingDigest,"expectedProviderBindingDigest");
    }
}
