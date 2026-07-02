package com.dylan.agent.metadata.config;

import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** D02_03 metadata instance configuration placeholder; not a runtime fact source. */
@ConfigurationProperties(prefix = "agent.metadata")
public class AgentMetadataProperties {

    private String bundleVersion;
    private String defaultProfileId;
    private Duration reloadValidationTimeout = Duration.ofSeconds(5);

    public String getBundleVersion() { return bundleVersion; }
    public void setBundleVersion(String bundleVersion) { this.bundleVersion = bundleVersion; }
    public String getDefaultProfileId() { return defaultProfileId; }
    public void setDefaultProfileId(String defaultProfileId) { this.defaultProfileId = defaultProfileId; }
    public Duration getReloadValidationTimeout() { return reloadValidationTimeout; }
    public void setReloadValidationTimeout(Duration reloadValidationTimeout) {
        this.reloadValidationTimeout = reloadValidationTimeout;
    }
}
