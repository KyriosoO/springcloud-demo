package com.dylan.agent.adapter.api.document.provider;

import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.adapter.api.operation.ProviderSafeIdentity;
import com.fasterxml.jackson.databind.MapperFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Objects;
import java.time.Instant;

/** Document Provider input/wire/binding/activation 的 canonical digest 实现。 */
public final class DocumentProviderCanonicalizer {
    private final ObjectMapper mapper;

    public DocumentProviderCanonicalizer(ObjectMapper mapper) {
        this.mapper = Objects.requireNonNull(mapper, "mapper must not be null").copy()
                .configure(MapperFeature.SORT_PROPERTIES_ALPHABETICALLY, true)
                .configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true);
    }

    public String inputDigest(Object input) {
        Objects.requireNonNull(input, "provider input must not be null");
        try {
            return digest(bytes("DPI-1"), mapper.writeValueAsBytes(input));
        } catch (Exception ex) {
            throw new IllegalArgumentException("document provider input is not canonicalizable", ex);
        }
    }

    public String wireRequestDigest(String wireVersion,
                                    String operationId,
                                    CapabilityOperationType operationType,
                                    long deadlineEpochMillis,
                                    String activationDigest,
                                    String providerBindingDigest,
                                    Object input) {
        return digestFields("DPW-1", requireNonBlank(wireVersion, "wireVersion"),
                requireNonBlank(operationId, "operationId"),
                Objects.requireNonNull(operationType, "operationType must not be null").value(),
                Long.toString(deadlineEpochMillis), requireDigest(activationDigest, "activationDigest"),
                requireDigest(providerBindingDigest, "providerBindingDigest"), inputDigest(input));
    }

    public String providerBindingDigest(CapabilityOperationType operationType,
                                        ProviderSafeIdentity provider,
                                        String adapterServiceIdentityRef,
                                        String adapterDeploymentRef,
                                        String vendorContractVersion,
                                        String templateOrModelBindingDigest) {
        Objects.requireNonNull(provider, "provider must not be null");
        return digestFields("DPB-1", Objects.requireNonNull(operationType).value(), provider.providerId(),
                provider.modelRef().orElse(""), requireNonBlank(adapterServiceIdentityRef, "adapterServiceIdentityRef"),
                requireNonBlank(adapterDeploymentRef, "adapterDeploymentRef"),
                requireNonBlank(vendorContractVersion, "vendorContractVersion"),
                requireDigest(templateOrModelBindingDigest, "templateOrModelBindingDigest"));
    }

    public String providerBindingDigest(DocumentProviderBindingReference binding) {
        Objects.requireNonNull(binding, "binding must not be null");
        return providerBindingDigest(binding.operationType(), binding.provider(), binding.adapterServiceIdentityRef(),
                binding.adapterDeploymentRef(), binding.vendorContractVersion(), binding.templateOrModelBindingDigest());
    }

    public String activationSnapshotDigest(CapabilityOperationType operationType,
                                           DocumentProviderActivationState state,
                                           DocumentProviderBindingReference binding,
                                           String wireContractVersion,
                                           String rolloutVersion,
                                           Instant validUntil) {
        return digestFields("DPA-1", Objects.requireNonNull(operationType).value(), Objects.requireNonNull(state).name(),
                binding == null ? "" : requireDigest(binding.canonicalDigest(), "providerBindingDigest"),
                requireNonBlank(wireContractVersion, "wireContractVersion"),
                requireNonBlank(rolloutVersion, "rolloutVersion"), Objects.requireNonNull(validUntil).toString());
    }

    public String activationSnapshotDigest(DocumentProviderActivationSnapshot snapshot) {
        Objects.requireNonNull(snapshot, "snapshot must not be null");
        return activationSnapshotDigest(snapshot.operationType(), snapshot.state(),
                snapshot.expectedProvider().orElse(null), snapshot.wireContractVersion(),
                snapshot.rolloutVersion(), snapshot.validUntil());
    }

    private static String digestFields(String... values) {
        byte[][] fields = java.util.Arrays.stream(values).map(DocumentProviderCanonicalizer::bytes)
                .toArray(byte[][]::new);
        return digest(fields);
    }

    private static String digest(byte[]... fields) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for (byte[] field : fields) {
                digest.update(ByteBuffer.allocate(Integer.BYTES).putInt(field.length).array());
                digest.update(field);
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (Exception ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }

    private static byte[] bytes(String value) { return value.getBytes(StandardCharsets.UTF_8); }
    private static String requireDigest(String value, String name) {
        if (value == null || !value.matches("[0-9a-f]{64}")) throw new IllegalArgumentException(name + " must be a SHA-256 digest");
        return value;
    }
    private static String requireNonBlank(String value, String name) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " must not be blank");
        return value;
    }
}
