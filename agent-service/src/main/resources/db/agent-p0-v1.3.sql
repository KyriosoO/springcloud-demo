-- 仅用于已有 P0 安装。
-- 在部署轮次与调用记录关联代码前执行一次。

ALTER TABLE agent_turn
  ADD COLUMN invocation_id VARCHAR(64) NULL AFTER conversation_id,
  ADD UNIQUE INDEX uk_agent_turn_invocation (invocation_id);
