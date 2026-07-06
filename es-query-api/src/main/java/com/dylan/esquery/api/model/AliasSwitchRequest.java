package com.dylan.esquery.api.model;

/** 文档读取 alias 切换或回滚请求。 */
public class AliasSwitchRequest {
	private String taskId;
	private String targetIndex;
	private String expectedPreviousIndex;
	private String validationDigest;
	private String operatorRef;

	public String getTaskId() { return taskId; }
	public void setTaskId(String taskId) { this.taskId = taskId; }
	public String getTargetIndex() { return targetIndex; }
	public void setTargetIndex(String targetIndex) { this.targetIndex = targetIndex; }
	public String getExpectedPreviousIndex() { return expectedPreviousIndex; }
	public void setExpectedPreviousIndex(String expectedPreviousIndex) { this.expectedPreviousIndex = expectedPreviousIndex; }
	public String getValidationDigest() { return validationDigest; }
	public void setValidationDigest(String validationDigest) { this.validationDigest = validationDigest; }
	public String getOperatorRef() { return operatorRef; }
	public void setOperatorRef(String operatorRef) { this.operatorRef = operatorRef; }
}
