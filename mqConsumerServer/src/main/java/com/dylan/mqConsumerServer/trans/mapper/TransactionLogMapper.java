package com.dylan.mqConsumerServer.trans.mapper;

import java.util.List;
import java.util.Set;

import com.dylan.common.model.trans.TransactionLog;

//@Mapper
public interface TransactionLogMapper {
	public void save(List<TransactionLog> list);

	public void deleteTimeoutProcessed();

	/*
	 * INSERT INTO transaction_log (trans_id, seq_no, payload, processed,
	 * created_at) <foreach collection="logs" item="log" separator=","> SELECT
	 * #{log.transId}, #{log.seqNo}, #{log.payload}, #{log.processed},
	 * #{log.createdAt} FROM dual WHERE NOT EXISTS ( SELECT 1 FROM transaction_log l
	 * WHERE l.trans_id = #{log.transId} AND l.seq_no = #{log.seqNo} ) </foreach>
	 */
	public void insertBatchIfNotExist(List<TransactionLog> list);

	public List<TransactionLog> fetchProcessing();

	public Set<String> fetchNewTransByIdentityAsSet();

	public void updateProcessed(List<TransactionLog> list);

}