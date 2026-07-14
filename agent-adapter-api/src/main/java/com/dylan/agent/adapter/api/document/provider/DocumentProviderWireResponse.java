package com.dylan.agent.adapter.api.document.provider;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
public record DocumentProviderWireResponse<T>(String wireContractVersion,String operationId,CapabilityOperationType operationType,String requestDigest,String activationDigest,DocumentProviderBindingReference providerBinding,T payload) {
    public DocumentProviderWireResponse {
        if(!"DPW-1".equals(wireContractVersion)||operationType==null||providerBinding==null||payload==null)
            throw new IllegalArgumentException("document provider wire response incomplete");
        DocumentProviderContractValidation.text(operationId,"operationId");
        DocumentProviderContractValidation.digest(requestDigest,"requestDigest");
        DocumentProviderContractValidation.digest(activationDigest,"activationDigest");
    }
}
