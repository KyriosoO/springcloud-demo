package com.dylan.agent.kernel.definition;

import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;

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
        this.reads = List.copyOf(reads);
        this.writes = List.copyOf(writes);
        validateNoDuplicateType();
    }

    public void validateNoDuplicateType() {
        var readTypes = reads.stream().map(ContextReadDeclaration::contextType).toList();
        var distinctRead = Set.copyOf(readTypes);
        if (distinctRead.size() != readTypes.size()) {
            throw new IllegalArgumentException("duplicate contextType in reads");
        }
        var writeTypes = writes.stream().map(ContextWriteDeclaration::contextType).toList();
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

}
