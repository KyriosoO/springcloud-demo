package com.dylan.agent.kernel.port.model;

import com.dylan.agent.api.contract.common.ContractRef;

import java.util.Arrays;
import java.util.Objects;

/**
 * ResultSecurityPort 返回的不可变安全结果。
 *
 * <p>该类型只携带 canonical bytes，不携带可变 typed candidate object，
 * 防止 Core/Lifecycle 在 ResultSecurity 之后绕过过滤或脱敏。</p>
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
