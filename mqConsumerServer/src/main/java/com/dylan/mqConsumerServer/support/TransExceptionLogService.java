package com.dylan.mqConsumerServer.support;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import com.dylan.common.db.util.DBBatchExecutor;
import com.dylan.common.model.trans.TransactionLog;
import com.dylan.mqConsumerServer.trans.mapper.TransactionLogMapper;

@Service
public class TransExceptionLogService {

	@Autowired
	DBBatchExecutor dbBatchExecutor;

	@Transactional(propagation = Propagation.REQUIRES_NEW)
	public void saveExceptionLog(List<TransactionLog> batch) {
		try {
			dbBatchExecutor.executeBatch(batch, TransactionLogMapper.class, TransactionLogMapper::saveException);
		} catch (Exception e) {
			e.printStackTrace();
		}
	}
}
