package com.dylan.agent.invocation.model;

import com.dylan.agent.invocation.model.KernelErrorCode;

import java.util.Objects;
import java.util.Optional;

/**
 * Request-scoped 取消信号源。
 *
 * <p>只有 Entry/Lifecycle 持有 source 实例，可通过 {@link #token()} 分发只读
 * {@link CancellationToken} 给 Core/Handler/Adapter。</p>
 *
 * <p>按照 D02_02 §2.4 设计：reason 只允许 CANCELLED 或 DEADLINE_EXCEEDED；
 * cancel 操作不可逆。</p>
 */
public final class CancellationSource {

    private volatile CancellationTokenImpl current;

    /**
     * 创建新取消信号源，初始为未取消状态。
     */
    public CancellationSource() {
        this.current = new CancellationTokenImpl(false, null);
    }

    /**
     * 返回当前只读令牌快照。
     */
    public CancellationToken token() {
        return current;
    }

    /**
     * 尝试取消。reason 必须是 CANCELLED 或 DEADLINE_EXCEEDED。
     *
     * @return true 如果此次调用成功写入取消状态，false 如果已被取消
     */
    public boolean cancel(KernelErrorCode safeReasonCode) {
        if (safeReasonCode != KernelErrorCode.CANCELLED
                && safeReasonCode != KernelErrorCode.DEADLINE_EXCEEDED) {
            throw new IllegalArgumentException(
                    "cancel reason must be CANCELLED or DEADLINE_EXCEEDED, got: "
                            + safeReasonCode);
        }
        CancellationTokenImpl currentSnap = this.current;
        if (currentSnap.isCancelled()) {
            return false;
        }
        this.current = new CancellationTokenImpl(true, safeReasonCode);
        return true;
    }

    // ── 内部不可变实现 ──

    private record CancellationTokenImpl(
            boolean cancelled,
            KernelErrorCode reason) implements CancellationToken {

        @Override
        public boolean isCancelled() { return cancelled; }

        @Override
        public Optional<KernelErrorCode> reasonCode() {
            return Optional.ofNullable(reason);
        }

        @Override
        public void throwIfCancelled() {
            if (cancelled) {
                throw new CancellationException(
                        Objects.requireNonNull(reason),
                        "Invocation cancelled: " + reason.name());
            }
        }
    }

    /**
     * 取消异常，携带安全错误码。
     */
    public static final class CancellationException extends RuntimeException {
        private final KernelErrorCode reasonCode;

        CancellationException(KernelErrorCode reasonCode, String message) {
            super(message);
            this.reasonCode = Objects.requireNonNull(reasonCode);
        }

        public KernelErrorCode reasonCode() { return reasonCode; }
    }
}
