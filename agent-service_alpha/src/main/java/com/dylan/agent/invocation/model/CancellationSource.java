package com.dylan.agent.invocation.model;

import com.dylan.agent.invocation.model.KernelErrorCode;

import java.util.Objects;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;

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

    private final CancellationTokenImpl token;

    /**
     * 创建新取消信号源，初始为未取消状态。
     */
    public CancellationSource() {
        this.token = new CancellationTokenImpl();
    }

    /**
     * 返回稳定的只读令牌视图；后续取消会对已分发的同一视图可见。
     */
    public CancellationToken token() {
        return token;
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
        return token.cancel(safeReasonCode);
    }

    // ── 内部线程安全实现 ──

    private static final class CancellationTokenImpl implements CancellationToken {

        private final AtomicReference<KernelErrorCode> reason = new AtomicReference<>();

        private boolean cancel(KernelErrorCode safeReasonCode) {
            return reason.compareAndSet(null, safeReasonCode);
        }

        @Override
        public boolean isCancelled() { return reason.get() != null; }

        @Override
        public Optional<KernelErrorCode> reasonCode() {
            return Optional.ofNullable(reason.get());
        }

        @Override
        public void throwIfCancelled() {
            KernelErrorCode safeReasonCode = reason.get();
            if (safeReasonCode != null) {
                throw new CancellationException(
                        safeReasonCode,
                        "Invocation cancelled: " + safeReasonCode.name());
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
