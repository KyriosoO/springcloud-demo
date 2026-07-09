package com.dylan.esquery.api.model;

/** 文档读取 alias 切换或回滚请求。 */
public class AliasSwitchRequest {
	private String taskId;
	private String targetIndex;
	private String expectedPreviousIndex;
	private String validationDigest;
	private String operatorRef;
	private String domain;
	private String materialType;
	private String profileVersion;
	private String indexVersion;
	private String goldSetVersion;
	private String validationReportId;

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
	public String getDomain() { return domain; }
	public void setDomain(String domain) { this.domain = domain; }
	public String getMaterialType() { return materialType; }
	public void setMaterialType(String materialType) { this.materialType = materialType; }
	public String getProfileVersion() { return profileVersion; }
	public void setProfileVersion(String profileVersion) { this.profileVersion = profileVersion; }
	public String getIndexVersion() { return indexVersion; }
	public void setIndexVersion(String indexVersion) { this.indexVersion = indexVersion; }
	public String getGoldSetVersion() { return goldSetVersion; }
	public void setGoldSetVersion(String goldSetVersion) { this.goldSetVersion = goldSetVersion; }
	public String getValidationReportId() { return validationReportId; }
	public void setValidationReportId(String validationReportId) { this.validationReportId = validationReportId; }
}
