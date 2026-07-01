package com.dylan.transaction.api.model;

import java.math.BigDecimal;
import java.util.Date;

public class Transaction {
	private String transId;
	private String transType;
	private Date transDate;
	private BigDecimal amount;
	private Date transDateGt;
	private Date transDateLt;
	private BigDecimal amountGt;
	private BigDecimal amountLt;
	private String transTypeContains;

	public String getTransId() {
		return transId;
	}

	public void setTransId(String transId) {
		this.transId = transId;
	}

	public String getTransType() {
		return transType;
	}

	public void setTransType(String transType) {
		this.transType = transType;
	}

	public Date getTransDate() {
		return transDate;
	}

	public void setTransDate(Date transDate) {
		this.transDate = transDate;
	}

	public BigDecimal getAmount() {
		return amount;
	}

	public void setAmount(BigDecimal amount) {
		this.amount = amount;
	}

	public Date getTransDateGt() {
		return transDateGt;
	}

	public void setTransDateGt(Date transDateGt) {
		this.transDateGt = transDateGt;
	}

	public Date getTransDateLt() {
		return transDateLt;
	}

	public void setTransDateLt(Date transDateLt) {
		this.transDateLt = transDateLt;
	}

	public BigDecimal getAmountGt() {
		return amountGt;
	}

	public void setAmountGt(BigDecimal amountGt) {
		this.amountGt = amountGt;
	}

	public BigDecimal getAmountLt() {
		return amountLt;
	}

	public void setAmountLt(BigDecimal amountLt) {
		this.amountLt = amountLt;
	}

	public String getTransTypeContains() {
		return transTypeContains;
	}

	public void setTransTypeContains(String transTypeContains) {
		this.transTypeContains = transTypeContains;
	}
}
