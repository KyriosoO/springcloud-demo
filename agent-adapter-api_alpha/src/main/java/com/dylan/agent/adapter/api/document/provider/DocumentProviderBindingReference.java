package com.dylan.agent.adapter.api.document.provider;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.adapter.api.operation.ProviderSafeIdentity;

public record DocumentProviderBindingReference(
        CapabilityOperationType operationType,
        ProviderSafeIdentity provider,
        String adapterServiceIdentityRef,
        String adapterDeploymentRef,
        String vendorContractVersion,
        String templateOrModelBindingDigest,
        String canonicalDigest) {
    public DocumentProviderBindingReference {
        if (operationType == null || provider == null || blank(adapterServiceIdentityRef)
                || blank(adapterDeploymentRef) || blank(vendorContractVersion)
                || !digest(templateOrModelBindingDigest) || !digest(canonicalDigest)) {
            throw new IllegalArgumentException("document provider binding invalid");
        }
    }
    private static boolean blank(String value) { return value == null || value.isBlank(); }
    private static boolean digest(String value) { return value != null && value.matches("[0-9a-f]{64}"); }
}
