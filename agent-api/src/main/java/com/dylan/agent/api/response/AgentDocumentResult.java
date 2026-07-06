package com.dylan.agent.api.response;

import com.fasterxml.jackson.annotation.JsonIgnore;
import java.util.List;

/** 文档能力最终安全结果。 */
public class AgentDocumentResult {

    private String answerText;
    private String summaryText;
    private List<String> summaryBullets;
    private List<AgentDocumentHit> hits;
    private List<AgentDocumentCitation> citations;
    private boolean partial;
    private AgentDocumentCoverage coverage;
    private DocumentGenerationStatus generationStatus;
    private GroundingStatus groundingStatus;
    private AgentDocumentCitationVerification citationVerification;
    private String candidateAnswerText;
    private String candidateSummaryText;
    private List<String> candidateSummaryBullets;

    public String getAnswerText() { return answerText; }
    public void setAnswerText(String answerText) { this.answerText = answerText; }
    public String getSummaryText() { return summaryText; }
    public void setSummaryText(String summaryText) { this.summaryText = summaryText; }
    public List<String> getSummaryBullets() { return summaryBullets; }
    public void setSummaryBullets(List<String> summaryBullets) { this.summaryBullets = summaryBullets; }
    public List<AgentDocumentHit> getHits() { return hits; }
    public void setHits(List<AgentDocumentHit> hits) { this.hits = hits; }
    public List<AgentDocumentCitation> getCitations() { return citations; }
    public void setCitations(List<AgentDocumentCitation> citations) { this.citations = citations; }
    public boolean isPartial() { return partial; }
    public void setPartial(boolean partial) { this.partial = partial; }
    public AgentDocumentCoverage getCoverage() { return coverage; }
    public void setCoverage(AgentDocumentCoverage coverage) { this.coverage = coverage; }
    public DocumentGenerationStatus getGenerationStatus() { return generationStatus; }
    public void setGenerationStatus(DocumentGenerationStatus generationStatus) { this.generationStatus = generationStatus; }
    public GroundingStatus getGroundingStatus() { return groundingStatus; }
    public void setGroundingStatus(GroundingStatus groundingStatus) { this.groundingStatus = groundingStatus; }
    public AgentDocumentCitationVerification getCitationVerification() { return citationVerification; }
    public void setCitationVerification(AgentDocumentCitationVerification citationVerification) { this.citationVerification = citationVerification; }
    @JsonIgnore
    public String getCandidateAnswerText() { return candidateAnswerText; }
    @JsonIgnore
    public void setCandidateAnswerText(String candidateAnswerText) { this.candidateAnswerText = candidateAnswerText; }
    @JsonIgnore
    public String getCandidateSummaryText() { return candidateSummaryText; }
    @JsonIgnore
    public void setCandidateSummaryText(String candidateSummaryText) { this.candidateSummaryText = candidateSummaryText; }
    @JsonIgnore
    public List<String> getCandidateSummaryBullets() { return candidateSummaryBullets; }
    @JsonIgnore
    public void setCandidateSummaryBullets(List<String> candidateSummaryBullets) { this.candidateSummaryBullets = candidateSummaryBullets; }
}
