package com.dylan.transaction.api.support;

import com.dylan.transaction.api.model.TransactionLog;

public class TransactionEvent {
	private TransactionLog log;

	public void set(TransactionLog log) {
		this.log = log;
	}

	public TransactionLog get() {
		return log;
	}
}
