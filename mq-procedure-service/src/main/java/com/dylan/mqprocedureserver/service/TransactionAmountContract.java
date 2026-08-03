package com.dylan.mqprocedureserver.service;

import java.math.BigDecimal;

import com.dylan.transaction.api.model.Transaction;

/** Exact amount boundary derived from the owned t_transaction.AMOUNT DECIMAL(50,2) column. */
final class TransactionAmountContract {
	static final int PRECISION = 50;
	static final int SCALE = 2;
	static final int INTEGER_DIGITS = PRECISION - SCALE;

	private TransactionAmountContract() {
	}

	static void validateSearchCondition(Transaction condition) {
		validate(condition.getAmount());
		validate(condition.getAmountGt());
		validate(condition.getAmountLt());
	}

	private static void validate(BigDecimal value) {
		if (value == null) {
			return;
		}
		int fractionalDigits = Math.max(value.scale(), 0);
		int integerDigits = Math.max(value.precision() - value.scale(), 0);
		if (fractionalDigits > SCALE || integerDigits > INTEGER_DIGITS || value.precision() > PRECISION) {
			throw new IllegalArgumentException("金额超出 DECIMAL(50,2) 精确查询范围。");
		}
	}
}
