package com.dylan.agent.adapter.api.document;

import java.util.List;

/** Adapter 返回的文档候选结果，最终文本仍需 ResultSecurity 过滤后生成或确认。 */
public class AdapterDocumentResult {

    private List<AdapterDocumentEvidence> hits;
    private List<AdapterDocumentEvidence> citations;
    private String candidateAnswerText;
    private String candidateSummaryText;
    private List<String> candidateSummaryBullets;
    private boolean partial;
    private int requestedDocumentCount;
    private int coveredDocumentCount;

    public List<AdapterDocumentEvidence> getHits() { return hits; }
    public void setHits(List<AdapterDocumentEvidence> hits) { this.hits = hits; }
    public List<AdapterDocumentEvidence> getCitations() { return citations; }
    public void setCitations(List<AdapterDocumentEvidence> citations) { this.citations = citations; }
    public String getCandidateAnswerText() { return candidateAnswerText; }
    public void setCandidateAnswerText(String candidateAnswerText) { this.candidateAnswerText = candidateAnswerText; }
    public String getCandidateSummaryText() { return candidateSummaryText; }
    public void setCandidateSummaryText(String candidateSummaryText) { this.candidateSummaryText = candidateSummaryText; }
    public List<String> getCandidateSummaryBullets() { return candidateSummaryBullets; }
    public void setCandidateSummaryBullets(List<String> candidateSummaryBullets) { this.candidateSummaryBullets = candidateSummaryBullets; }
    public boolean isPartial() { return partial; }
    public void setPartial(boolean partial) { this.partial = partial; }
    public int getRequestedDocumentCount() { return requestedDocumentCount; }
    public void setRequestedDocumentCount(int requestedDocumentCount) { this.requestedDocumentCount = requestedDocumentCount; }
    public int getCoveredDocumentCount() { return coveredDocumentCount; }
    public void setCoveredDocumentCount(int coveredDocumentCount) { this.coveredDocumentCount = coveredDocumentCount; }
}
