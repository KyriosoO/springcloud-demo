package com.dylan.documentprovider;

import org.springframework.boot.context.properties.ConfigurationProperties;
import java.time.Duration;
import org.springframework.beans.factory.InitializingBean;

@ConfigurationProperties(prefix = "document-provider.activation-feed")
public class DocumentProviderActivationFeedProperties implements InitializingBean {
    private String baseUrl = "http://agent-service";
    private String consumerId = "document-provider-adapter";
    private String deploymentDigest;
    private Duration refreshDelay = Duration.ofSeconds(1);
    private Duration maxDistributionStaleness = Duration.ofSeconds(5);
    public String getBaseUrl(){return baseUrl;} public void setBaseUrl(String value){baseUrl=value;}
    public String getConsumerId(){return consumerId;} public void setConsumerId(String value){consumerId=value;}
    public String getDeploymentDigest(){return deploymentDigest;} public void setDeploymentDigest(String value){deploymentDigest=value;}
    public Duration getRefreshDelay(){return refreshDelay;} public void setRefreshDelay(Duration value){refreshDelay=value;}
    public Duration getMaxDistributionStaleness(){return maxDistributionStaleness;} public void setMaxDistributionStaleness(Duration value){maxDistributionStaleness=value;}
    @Override public void afterPropertiesSet(){if(baseUrl==null||baseUrl.isBlank()||consumerId==null||consumerId.isBlank()||deploymentDigest==null||!deploymentDigest.matches("[0-9a-f]{64}")||refreshDelay==null||refreshDelay.isZero()||refreshDelay.isNegative()||maxDistributionStaleness==null||maxDistributionStaleness.isZero()||maxDistributionStaleness.isNegative())throw new IllegalStateException("document provider activation feed properties invalid");}
}
