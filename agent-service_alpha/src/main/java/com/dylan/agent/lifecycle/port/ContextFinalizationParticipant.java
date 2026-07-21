package com.dylan.agent.lifecycle.port;

import com.dylan.agent.kernel.port.model.ApprovedContextWrite;

import java.util.List;

/**
 * Context finalization participant — D02_03 实现。
 *
 * <p>事务传播为 MANDATORY，使用同一 Agent DataSource。不能开始独立事务，
 * 不能形成自己的终态。Lifecycle 在 finalization 事务内调用。</p>
 *
 * <p>按照 D02_02 §6.1 设计；实现由 D02_03 拥有。</p>
 */
public interface ContextFinalizationParticipant {

    /**
     * 在同一事务中持久化已审批的 Context writes。
     *
     * @param writes 已审批的 Context write 列表
     */
    void persist(List<ApprovedContextWrite> writes);
}
