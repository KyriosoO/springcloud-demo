package com.dylan.mqProcedureServer.service;

import org.apache.rocketmq.spring.annotation.RocketMQTransactionListener;
import org.apache.rocketmq.spring.core.RocketMQLocalTransactionListener;
import org.apache.rocketmq.spring.core.RocketMQLocalTransactionState;
import org.springframework.messaging.Message;
import org.springframework.stereotype.Component;

@Component
@RocketMQTransactionListener
public class OrderTransactionListener implements RocketMQLocalTransactionListener {

	@Override
	public RocketMQLocalTransactionState executeLocalTransaction(Message msg, Object arg) {
		System.out.println("执行本地事务: " + arg);
		try {
			// 模拟订单入库
			boolean success = true;
			msg.getPayload();
			if (success) {
				return RocketMQLocalTransactionState.COMMIT;
			}
			return RocketMQLocalTransactionState.ROLLBACK;
		} catch (Exception e) {
			return RocketMQLocalTransactionState.UNKNOWN;
		}
	}

	@Override
	public RocketMQLocalTransactionState checkLocalTransaction(Message msg) {
		System.out.println("事务回查");
		// 查询数据库订单状态
		return RocketMQLocalTransactionState.COMMIT;
	}

}
