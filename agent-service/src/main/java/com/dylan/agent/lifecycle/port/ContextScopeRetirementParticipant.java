package com.dylan.agent.lifecycle.port;

import com.dylan.agent.invocation.model.ConversationScope;

import java.time.Instant;

/**
 * Context scope retirement participant — D02_03 实现。
 *
 * <p>唯一方法 retire：幂等提交 readable=false。
 * 只服务 Conversation 清理的 fail-closed 前置，不删除 Context、不处理 RunScope，
 * 不参与 SUCCESS finalization。</p>
 *
 * <p>按照 D02_02 §6.1 设计；实现由 D02_03 拥有。</p>
 */
public interface ContextScopeRetirementParticipant {

    /**
     * 对指定 scope 执行退出（readable=false），幂等。
     */
    void retire(ConversationScope scope, Instant now);
}
