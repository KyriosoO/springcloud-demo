package com.dylan.documentprovider;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

/** Adapter 侧只收紧不扩大业务预算的 operational cap。 */
@ConfigurationProperties(prefix = "document-provider.operation")
public final class DocumentProviderOperationProperties implements InitializingBean {
    private Duration maxStageHorizon = Duration.ofSeconds(30);
    private int maxItems = 512;
    private int maxTextChars = 100_000;
    private int maxTotalTextChars = 1_000_000;
    private int maxEmbeddingDimension = 8_192;
    private long maxRequestBytes = 2_000_000L;

    public Duration getMaxStageHorizon() { return maxStageHorizon; }
    public void setMaxStageHorizon(Duration value) { maxStageHorizon = value; }
    public int getMaxItems() { return maxItems; }
    public void setMaxItems(int value) { maxItems = value; }
    public int getMaxTextChars() { return maxTextChars; }
    public void setMaxTextChars(int value) { maxTextChars = value; }
    public int getMaxTotalTextChars() { return maxTotalTextChars; }
    public void setMaxTotalTextChars(int value) { maxTotalTextChars = value; }
    public int getMaxEmbeddingDimension() { return maxEmbeddingDimension; }
    public void setMaxEmbeddingDimension(int value) { maxEmbeddingDimension = value; }
    public long getMaxRequestBytes() { return maxRequestBytes; }
    public void setMaxRequestBytes(long value) { maxRequestBytes = value; }

    @Override
    public void afterPropertiesSet() {
        if (maxStageHorizon == null || maxStageHorizon.isZero() || maxStageHorizon.isNegative()
                || maxItems <= 0 || maxTextChars <= 0 || maxTotalTextChars < maxTextChars
                || maxEmbeddingDimension <= 0 || maxRequestBytes <= 0
                || maxRequestBytes >= Integer.MAX_VALUE) {
            throw new IllegalStateException("document provider operation properties invalid");
        }
    }
}
