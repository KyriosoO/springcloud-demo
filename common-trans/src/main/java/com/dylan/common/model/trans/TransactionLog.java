package com.dylan.common.model.trans;

import java.util.Date;
import java.util.Objects;

public class TransactionLog {
	private String transId;
	private Long seqNo;
	private boolean processed;
	private String payload;
	private Date createdAt;

	public String getTransId() {
		return transId;
	}

	public void setTransId(String transId) {
		this.transId = transId;
	}

	public Long getSeqNo() {
		return seqNo;
	}

	public boolean isProcessed() {
		return processed;
	}

	public void setProcessed(boolean processed) {
		this.processed = processed;
	}

	public void setSeqNo(Long seqNo) {
		this.seqNo = seqNo;
	}

	public String getPayload() {
		return payload;
	}

	public void setPayload(String payload) {
		this.payload = payload;
	}

	public Date getCreatedAt() {
		return createdAt;
	}

	public void setCreatedAt(Date createdAt) {
		this.createdAt = createdAt;
	}

	@Override
	public boolean equals(Object o) {
		if (this == o)
			return true;
		if (!(o instanceof TransactionLog))
			return false;
		TransactionLog that = (TransactionLog) o;
		return Objects.equals(transId, that.transId) && Objects.equals(seqNo, that.seqNo);
	}

	@Override
	public int hashCode() {
		return Objects.hash(transId, seqNo);
	}
}
