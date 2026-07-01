package com.dylan.agent.conversation;

/**
 * 只读 Turn 句柄，隔离 Orchestrator 和持久化实体。
 */
public record TurnHandle(String turnId) {
}
