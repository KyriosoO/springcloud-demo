package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * D04 canonical domain metadata 绑定。
 *
 * <p>该类刻意保持可变，只用于 Spring composition boundary。
 * 所有运行时消费者都使用 D04 validator 构建的不可变实例：
 * {@link CanonicalDomainCatalog}/{@link AdapterRegistrationSet}。</p>
 */
@ConfigurationProperties(prefix = "agent.domain-metadata")
public class DomainMetadataProperties {

    private String catalogVersion;
    private String adapterRegistrationVersion;
    private Map<String, DomainProperties> domains = new LinkedHashMap<>();
    private List<RegistrationProperties> registrations = new ArrayList<>();

    public String getCatalogVersion() { return catalogVersion; }
    public void setCatalogVersion(String catalogVersion) { this.catalogVersion = catalogVersion; }
    public String getAdapterRegistrationVersion() { return adapterRegistrationVersion; }
    public void setAdapterRegistrationVersion(String adapterRegistrationVersion) {
        this.adapterRegistrationVersion = adapterRegistrationVersion;
    }
    public Map<String, DomainProperties> getDomains() { return domains; }
    public void setDomains(Map<String, DomainProperties> domains) { this.domains = domains; }
    public List<RegistrationProperties> getRegistrations() { return registrations; }
    public void setRegistrations(List<RegistrationProperties> registrations) { this.registrations = registrations; }

    public static class DomainProperties {
        private List<String> aliases = new ArrayList<>();
        private String description;
        private Map<String, List<String>> defaultSelectFieldsByRole = new LinkedHashMap<>();
        private Map<String, FieldProperties> fields = new LinkedHashMap<>();
        private Map<String, RoleCapabilityProperties> roleCapabilities = new LinkedHashMap<>();

        public List<String> getAliases() { return aliases; }
        public void setAliases(List<String> aliases) { this.aliases = aliases; }
        public String getDescription() { return description; }
        public void setDescription(String description) { this.description = description; }
        public Map<String, List<String>> getDefaultSelectFieldsByRole() { return defaultSelectFieldsByRole; }
        public void setDefaultSelectFieldsByRole(Map<String, List<String>> defaultSelectFieldsByRole) {
            this.defaultSelectFieldsByRole = defaultSelectFieldsByRole;
        }
        public Map<String, FieldProperties> getFields() { return fields; }
        public void setFields(Map<String, FieldProperties> fields) { this.fields = fields; }
        public Map<String, RoleCapabilityProperties> getRoleCapabilities() { return roleCapabilities; }
        public void setRoleCapabilities(Map<String, RoleCapabilityProperties> roleCapabilities) {
            this.roleCapabilities = roleCapabilities;
        }
    }

    public static class FieldProperties {
        private List<String> aliases = new ArrayList<>();
        private String description;
        private AgentFieldType type;
        private String unit;
        private String valueFormat;
        private Integer maxLength;
        private Integer precision;
        private Integer scale;

        public List<String> getAliases() { return aliases; }
        public void setAliases(List<String> aliases) { this.aliases = aliases; }
        public String getDescription() { return description; }
        public void setDescription(String description) { this.description = description; }
        public AgentFieldType getType() { return type; }
        public void setType(AgentFieldType type) { this.type = type; }
        public String getUnit() { return unit; }
        public void setUnit(String unit) { this.unit = unit; }
        public String getValueFormat() { return valueFormat; }
        public void setValueFormat(String valueFormat) { this.valueFormat = valueFormat; }
        public Integer getMaxLength() { return maxLength; }
        public void setMaxLength(Integer maxLength) { this.maxLength = maxLength; }
        public Integer getPrecision() { return precision; }
        public void setPrecision(Integer precision) { this.precision = precision; }
        public Integer getScale() { return scale; }
        public void setScale(Integer scale) { this.scale = scale; }
    }

    public static class RoleCapabilityProperties {
        private Set<String> fields = new LinkedHashSet<>();
        private Map<String, Set<AgentOperator>> operatorsByField = new LinkedHashMap<>();
        private Map<String, Set<AggregateFunction>> functionsByField = new LinkedHashMap<>();
        private Integer maxPageSize;
        private Integer maxResultRows;

        public Set<String> getFields() { return fields; }
        public void setFields(Set<String> fields) { this.fields = fields; }
        public Map<String, Set<AgentOperator>> getOperatorsByField() { return operatorsByField; }
        public void setOperatorsByField(Map<String, Set<AgentOperator>> operatorsByField) {
            this.operatorsByField = operatorsByField;
        }
        public Map<String, Set<AggregateFunction>> getFunctionsByField() { return functionsByField; }
        public void setFunctionsByField(Map<String, Set<AggregateFunction>> functionsByField) {
            this.functionsByField = functionsByField;
        }
        public Integer getMaxPageSize() { return maxPageSize; }
        public void setMaxPageSize(Integer maxPageSize) { this.maxPageSize = maxPageSize; }
        public Integer getMaxResultRows() { return maxResultRows; }
        public void setMaxResultRows(Integer maxResultRows) { this.maxResultRows = maxResultRows; }
    }

    public static class RegistrationProperties {
        private String registrationId;
        private String role;
        private String domain;
        private Class<?> portType;
        private String portBeanName;
        private String catalogVersion;
        private String registrationVersion;

        public String getRegistrationId() { return registrationId; }
        public void setRegistrationId(String registrationId) { this.registrationId = registrationId; }
        public String getRole() { return role; }
        public void setRole(String role) { this.role = role; }
        public String getDomain() { return domain; }
        public void setDomain(String domain) { this.domain = domain; }
        public Class<?> getPortType() { return portType; }
        public void setPortType(Class<?> portType) { this.portType = portType; }
        public String getPortBeanName() { return portBeanName; }
        public void setPortBeanName(String portBeanName) { this.portBeanName = portBeanName; }
        public String getCatalogVersion() { return catalogVersion; }
        public void setCatalogVersion(String catalogVersion) { this.catalogVersion = catalogVersion; }
        public String getRegistrationVersion() { return registrationVersion; }
        public void setRegistrationVersion(String registrationVersion) { this.registrationVersion = registrationVersion; }
    }
}
