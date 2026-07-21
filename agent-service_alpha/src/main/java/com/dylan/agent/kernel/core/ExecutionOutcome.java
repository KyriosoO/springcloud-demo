package com.dylan.agent.kernel.core;

/**
 * Core 返回 Lifecycle 的内部候选结果。
 * 不包含持久化终态或 API DTO。
 */
public sealed interface ExecutionOutcome permits ExecutionSuccess, ExecutionFailure {
}
