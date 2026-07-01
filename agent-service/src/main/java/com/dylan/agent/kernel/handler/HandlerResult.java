package com.dylan.agent.kernel.handler;

import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 * Handler 返回的候选结果和 Context write 声明。
 */
public final class HandlerResult<O> {

    private final O output;
    private final List<Object> contextWrites; // List<ContextWriteCandidate> after D02_03

    private HandlerResult(O output, List<Object> contextWrites) {
        this.output = Objects.requireNonNull(output);
        this.contextWrites = List.copyOf(contextWrites != null ? contextWrites : List.of());
    }

    public static <O> HandlerResult<O> of(O output) {
        return new HandlerResult<>(output, List.of());
    }

    public static <O> HandlerResult<O> of(O output, List<Object> contextWrites) {
        return new HandlerResult<>(output, contextWrites);
    }

    public O output() { return output; }
    public List<Object> contextWrites() { return contextWrites; }
}
