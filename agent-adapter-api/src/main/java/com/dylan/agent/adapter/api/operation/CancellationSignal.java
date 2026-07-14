package com.dylan.agent.adapter.api.operation;

/** 下游只读取消信号；取消写权限仍属于入口与 Lifecycle。 */
@FunctionalInterface
public interface CancellationSignal {

    boolean isCancelled();
}
