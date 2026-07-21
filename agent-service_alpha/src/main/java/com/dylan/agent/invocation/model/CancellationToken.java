package com.dylan.agent.invocation.model;

import com.dylan.agent.invocation.model.KernelErrorCode;

import java.util.Optional;

/**
 * 取消令牌接口。Core/Handler/Adapter 只能持有 token 查看状态。
 * 只有 Entry/Lifecycle 持有 CancellationSource 可以写入取消信号。
 *
 * <p>按照 D02_02 §2.4 设计。</p>
 */
public interface CancellationToken {

    /** 是否已被取消。 */
    boolean isCancelled();

    /** 取消原因码（如果已取消）。 */
    Optional<KernelErrorCode> reasonCode();

    /** 如果已取消则抛出 CancellationException。 */
    void throwIfCancelled();
}
