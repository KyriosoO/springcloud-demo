package com.dylan.agent.kernel.port.model;

import com.dylan.agent.api.contract.common.ContractRef;

import java.util.Arrays;
import java.util.Objects;

/**
 * Immutable secured result returned by ResultSecurityPort.
 *
 * <p>It carries canonical bytes instead of a mutable typed candidate object, so
 * Core/Lifecycle cannot bypass filtering or masking after result security.</p>
 */
public final class SecuredResult {

    private final ContractRef outputContract;
    private final byte[] canonicalPayload;
    private final String safeMessage;
    private final String safeSummary;

    public SecuredResult(ContractRef outputContract,
                         byte[] canonicalPayload,
                         String safeMessage,
                         String safeSummary) {
        this.outputContract = Objects.requireNonNull(outputContract, "outputContract must not be null");
        this.canonicalPayload = copyNonEmpty(canonicalPayload, "canonicalPayload");
        this.safeMessage = requireNonBlank(safeMessage, "safeMessage");
        this.safeSummary = requireNonBlank(safeSummary, "safeSummary");
    }

    public ContractRef outputContract() { return outputContract; }
    public byte[] canonicalPayload() { return Arrays.copyOf(canonicalPayload, canonicalPayload.length); }
    public String safeMessage() { return safeMessage; }
    public String safeSummary() { return safeSummary; }

    private static byte[] copyNonEmpty(byte[] value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        if (value.length == 0) {
            throw new IllegalArgumentException(name + " must not be empty");
        }
        return Arrays.copyOf(value, value.length);
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
