package com.dylan.common.security;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "common.security.secrets")
public class SecretProperties {

	private List<SecretSourceType> sourceOrder = new ArrayList<>(List.of(SecretSourceType.ENVIRONMENT,
			SecretSourceType.CONFIG));
	private boolean allowConfigValues;
	private boolean failFast = true;
	private PurposeProperties jwt = new PurposeProperties("ACTIVE");
	private PurposeProperties agentServiceJwt = new PurposeProperties("ACTIVE");
	private PurposeProperties agentPayload = new PurposeProperties("ACTIVE");

	public List<SecretSourceType> getSourceOrder() {
		return sourceOrder;
	}

	public void setSourceOrder(List<SecretSourceType> sourceOrder) {
		this.sourceOrder = sourceOrder == null ? new ArrayList<>() : new ArrayList<>(sourceOrder);
	}

	public boolean isAllowConfigValues() {
		return allowConfigValues;
	}

	public void setAllowConfigValues(boolean allowConfigValues) {
		this.allowConfigValues = allowConfigValues;
	}

	public boolean isFailFast() {
		return failFast;
	}

	public void setFailFast(boolean failFast) {
		this.failFast = failFast;
	}

	public PurposeProperties getJwt() {
		return jwt;
	}

	public void setJwt(PurposeProperties jwt) {
		this.jwt = jwt == null ? new PurposeProperties("ACTIVE") : jwt;
	}

	public PurposeProperties getAgentPayload() {
		return agentPayload;
	}

	public PurposeProperties getAgentServiceJwt() {
		return agentServiceJwt;
	}

	public void setAgentServiceJwt(PurposeProperties agentServiceJwt) {
		this.agentServiceJwt = agentServiceJwt == null ? new PurposeProperties("ACTIVE") : agentServiceJwt;
	}

	public void setAgentPayload(PurposeProperties agentPayload) {
		this.agentPayload = agentPayload == null ? new PurposeProperties("ACTIVE") : agentPayload;
	}

	public static class PurposeProperties {
		private String activeKeyId;
		private List<String> previousKeyIds = new ArrayList<>();
		private Map<String, KeyProperties> keys = new LinkedHashMap<>();

		public PurposeProperties() {
			this("ACTIVE");
		}

		public PurposeProperties(String activeKeyId) {
			this.activeKeyId = activeKeyId;
			this.keys.put(activeKeyId, new KeyProperties());
		}

		public String getActiveKeyId() {
			return activeKeyId;
		}

		public void setActiveKeyId(String activeKeyId) {
			this.activeKeyId = activeKeyId;
		}

		public List<String> getPreviousKeyIds() {
			return previousKeyIds;
		}

		public void setPreviousKeyIds(List<String> previousKeyIds) {
			this.previousKeyIds = previousKeyIds == null ? new ArrayList<>() : new ArrayList<>(previousKeyIds);
		}

		public Map<String, KeyProperties> getKeys() {
			return keys;
		}

		public void setKeys(Map<String, KeyProperties> keys) {
			this.keys = keys == null ? new LinkedHashMap<>() : new LinkedHashMap<>(keys);
		}
	}

	public static class KeyProperties {
		private String env;
		private String value;

		public String getEnv() {
			return env;
		}

		public void setEnv(String env) {
			this.env = env;
		}

		public String getValue() {
			return value;
		}

		public void setValue(String value) {
			this.value = value;
		}
	}
}
