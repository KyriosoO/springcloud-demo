package com.dylan.esquery.document;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

@ConfigurationProperties(prefix = "document-rebuild")
public class DocumentRebuildProperties {
    private int pageSize = 200;
    private int maxBulkAttempts = 3;
    private int chunkWindowCodePoints = 1200;
    private int chunkOverlapCodePoints = 200;
    private int maxDocumentCodePoints = 2_000_000;
    private Duration leaseDuration = Duration.ofSeconds(30);
    private Duration taskTimeout = Duration.ofHours(2);
    private Duration pollDelay = Duration.ofSeconds(2);
    public int getPageSize() { return pageSize; } public void setPageSize(int value) { pageSize = value; }
    public int getMaxBulkAttempts() { return maxBulkAttempts; } public void setMaxBulkAttempts(int value) { maxBulkAttempts = value; }
    public int getChunkWindowCodePoints() { return chunkWindowCodePoints; } public void setChunkWindowCodePoints(int value) { chunkWindowCodePoints = value; }
    public int getChunkOverlapCodePoints() { return chunkOverlapCodePoints; } public void setChunkOverlapCodePoints(int value) { chunkOverlapCodePoints = value; }
    public int getMaxDocumentCodePoints() { return maxDocumentCodePoints; } public void setMaxDocumentCodePoints(int value) { maxDocumentCodePoints = value; }
    public Duration getLeaseDuration() { return leaseDuration; } public void setLeaseDuration(Duration value) { leaseDuration = value; }
    public Duration getTaskTimeout() { return taskTimeout; } public void setTaskTimeout(Duration value) { taskTimeout = value; }
    public Duration getPollDelay() { return pollDelay; } public void setPollDelay(Duration value) { pollDelay = value; }
}
