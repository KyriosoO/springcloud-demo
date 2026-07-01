package com.dylan.agent.conversation;

/**
 * 只读 Conversation 句柄，隔离 Orchestrator 和持久化实体。
 */
public record ConversationHandle(String conversationId) {
}
