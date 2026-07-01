package com.dylan.agent.kernel.definition;

import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextView;

import java.time.Duration;
import java.util.List;
import java.util.Objects;
import java.util.Set;

/**
 * Registration 内 capability 所需的 Context 访问声明。
 *
 * <p>只引用 Java ContractRef，不复制 payload 字段结构。
 * Profile/Policy/Permission 只能收紧。
 */
public final class ContextAccessDeclaration {

    private final List<ContextReadDeclaration> reads;
    private final List<ContextWriteDeclaration> writes;

    public ContextAccessDeclaration(List<ContextReadDeclaration> reads,
                                     List<ContextWriteDeclaration> writes) {
        Objects.requireNonNull(reads);
        Objects.requireNonNull(writes);
        validateNoDuplicateType(reads, writes);
        this.reads = List.copyOf(reads);
        this.writes = List.copyOf(writes);
    }

    private static void validateNoDuplicateType(List<ContextReadDeclaration> r,
                                                 List<ContextWriteDeclaration> w) {
        var readTypes = r.stream().map(ContextReadDeclaration::contextType).toList();
        var distinctRead = Set.copyOf(readTypes);
        if (distinctRead.size() != readTypes.size()) {
            throw new IllegalArgumentException("duplicate contextType in reads");
        }
        var writeTypes = w.stream().map(ContextWriteDeclaration::contextType).toList();
        var distinctWrite = Set.copyOf(writeTypes);
        if (distinctWrite.size() != writeTypes.size()) {
            throw new IllegalArgumentException("duplicate contextType in writes");
        }
    }

    public List<ContextReadDeclaration> reads() { return reads; }
    public List<ContextWriteDeclaration> writes() { return writes; }

    public ContextReadDeclaration read(RuntimeContextType type) {
        return reads.stream().filter(r -> r.contextType() == type).findFirst().orElse(null);
    }

    public ContextWriteDeclaration write(RuntimeContextType type) {
        return writes.stream().filter(w -> w.contextType() == type).findFirst().orElse(null);
    }

    // ── nested declarations ──

    public record ContextReadDeclaration(
            RuntimeContextType contextType,
            ContractRef contractRef,
            Class<? extends RuntimeContextView> payloadType,
            boolean required,
            Set<String> readableFields) {
        public ContextReadDeclaration {
            Objects.requireNonNull(contextType);
            Objects.requireNonNull(contractRef);
            Objects.requireNonNull(payloadType);
            Objects.requireNonNull(readableFields);
        }
    }

    public record ContextWriteDeclaration(
            RuntimeContextType contextType,
            ContractRef contractRef,
            Class<? extends RuntimeContextView> payloadType,
            Duration maxTtl,
            Set<String> writableFields) {
        public ContextWriteDeclaration {
            Objects.requireNonNull(contextType);
            Objects.requireNonNull(contractRef);
            Objects.requireNonNull(payloadType);
            Objects.requireNonNull(maxTtl);
            Objects.requireNonNull(writableFields);
        }
    }
}
