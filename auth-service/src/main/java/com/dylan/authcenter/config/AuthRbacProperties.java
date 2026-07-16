package com.dylan.authcenter.config;

import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * auth-service 当前阶段的配置型 RBAC 数据源。
 *
 * <p>用户只绑定角色，Agent 权限通过角色引用命名权限模板。后续切换数据库时，
 * 应保持 UserService 和 AgentPermissionProjectionService 的对外契约不变。</p>
 */
@Component
@ConfigurationProperties(prefix = "auth.rbac")
public class AuthRbacProperties implements InitializingBean {

    private String ruleVersion;
    private Map<String, UserDefinition> users = new LinkedHashMap<>();
    private Map<String, RoleDefinition> roles = new LinkedHashMap<>();
    private Map<String, PermissionProfile> permissionProfiles = new LinkedHashMap<>();

    public String getRuleVersion() {
        return ruleVersion;
    }

    public void setRuleVersion(String ruleVersion) {
        this.ruleVersion = ruleVersion;
    }

    public Map<String, UserDefinition> getUsers() {
        return users;
    }

    public void setUsers(Map<String, UserDefinition> users) {
        this.users = users == null ? new LinkedHashMap<>() : new LinkedHashMap<>(users);
    }

    public Map<String, RoleDefinition> getRoles() {
        return roles;
    }

    public void setRoles(Map<String, RoleDefinition> roles) {
        this.roles = roles == null ? new LinkedHashMap<>() : new LinkedHashMap<>(roles);
    }

    public Map<String, PermissionProfile> getPermissionProfiles() {
        return permissionProfiles;
    }

    public void setPermissionProfiles(Map<String, PermissionProfile> permissionProfiles) {
        this.permissionProfiles = permissionProfiles == null
                ? new LinkedHashMap<>() : new LinkedHashMap<>(permissionProfiles);
    }

    @Override
    public void afterPropertiesSet() {
        requireText(ruleVersion, "auth.rbac.rule-version");
        if (users.isEmpty()) {
            throw new IllegalStateException("auth.rbac.users must not be empty");
        }
        if (roles.isEmpty()) {
            throw new IllegalStateException("auth.rbac.roles must not be empty");
        }
        users.forEach((userId, user) -> {
            requireText(userId, "auth.rbac.users key");
            if (user == null) {
                throw new IllegalStateException("auth.rbac user definition must not be null: " + userId);
            }
            requireText(user.password, "auth.rbac.users." + userId + ".password");
            if (user.roles.isEmpty()) {
                throw new IllegalStateException("auth.rbac user roles must not be empty: " + userId);
            }
            user.roles.forEach(role -> {
                if (!roles.containsKey(role)) {
                    throw new IllegalStateException("unknown RBAC role for user " + userId + ": " + role
                            + "; configured roles=" + roles.keySet());
                }
            });
        });
        roles.forEach((roleId, role) -> {
            requireText(roleId, "auth.rbac.roles key");
            if (role == null) {
                throw new IllegalStateException("auth.rbac role definition must not be null: " + roleId);
            }
            if (hasText(role.permissionProfile) && !permissionProfiles.containsKey(role.permissionProfile)) {
                throw new IllegalStateException(
                        "unknown permission profile for role " + roleId + ": " + role.permissionProfile);
            }
        });
        permissionProfiles.forEach(this::validateProfile);
    }

    private void validateProfile(String profileId, PermissionProfile profile) {
        requireText(profileId, "auth.rbac.permission-profiles key");
        if (profile == null) {
            throw new IllegalStateException("permission profile must not be null: " + profileId);
        }
        profile.filterableFields.keySet().forEach(domain -> requireDomain(profileId, profile, domain));
        profile.displayableFields.keySet().forEach(domain -> requireDomain(profileId, profile, domain));
        profile.allowedOperators.keySet().forEach(key -> requireFieldKey(profileId, profile, key));
        profile.allowedFunctions.keySet().forEach(key -> requireFieldKey(profileId, profile, key));
    }

    private void requireDomain(String profileId, PermissionProfile profile, String domain) {
        if (!profile.allowedDomains.contains(domain)) {
            throw new IllegalStateException(
                    "permission profile " + profileId + " references field domain outside allowed-domains: " + domain);
        }
    }

    private void requireFieldKey(String profileId, PermissionProfile profile, String fieldKey) {
        int separator = fieldKey == null ? -1 : fieldKey.indexOf('.');
        if (separator <= 0 || separator != fieldKey.lastIndexOf('.')) {
            throw new IllegalStateException("invalid field rule key in permission profile " + profileId + ": " + fieldKey);
        }
        requireDomain(profileId, profile, fieldKey.substring(0, separator));
    }

    private static void requireText(String value, String name) {
        if (!hasText(value)) {
            throw new IllegalStateException(name + " must not be blank");
        }
    }

    private static boolean hasText(String value) {
        return value != null && !value.isBlank();
    }

    public static class UserDefinition {
        private String password;
        private Set<String> roles = new LinkedHashSet<>();

        public String getPassword() {
            return password;
        }

        public void setPassword(String password) {
            this.password = password;
        }

        public Set<String> getRoles() {
            return roles;
        }

        public void setRoles(Set<String> roles) {
            this.roles = roles == null ? new LinkedHashSet<>() : new LinkedHashSet<>(roles);
        }
    }

    public static class RoleDefinition {
        private String permissionProfile;

        public String getPermissionProfile() {
            return permissionProfile;
        }

        public void setPermissionProfile(String permissionProfile) {
            this.permissionProfile = permissionProfile;
        }
    }

    public static class PermissionProfile {
        private Set<String> allowedCapabilityIds = new LinkedHashSet<>();
        private Set<String> allowedDomains = new LinkedHashSet<>();
        private Map<String, Set<String>> filterableFields = new LinkedHashMap<>();
        private Map<String, Set<String>> displayableFields = new LinkedHashMap<>();
        private Map<String, Set<String>> allowedOperators = new LinkedHashMap<>();
        private Map<String, Set<String>> allowedFunctions = new LinkedHashMap<>();
        private Set<String> readableContextTypes = new LinkedHashSet<>();
        private Set<String> writableContextTypes = new LinkedHashSet<>();
        private Map<String, String> attributes = new LinkedHashMap<>();

        public Set<String> getAllowedCapabilityIds() { return allowedCapabilityIds; }
        public void setAllowedCapabilityIds(Set<String> values) { allowedCapabilityIds = copySet(values); }
        public Set<String> getAllowedDomains() { return allowedDomains; }
        public void setAllowedDomains(Set<String> values) { allowedDomains = copySet(values); }
        public Map<String, Set<String>> getFilterableFields() { return filterableFields; }
        public void setFilterableFields(Map<String, Set<String>> values) { filterableFields = copyMap(values); }
        public Map<String, Set<String>> getDisplayableFields() { return displayableFields; }
        public void setDisplayableFields(Map<String, Set<String>> values) { displayableFields = copyMap(values); }
        public Map<String, Set<String>> getAllowedOperators() { return allowedOperators; }
        public void setAllowedOperators(Map<String, Set<String>> values) { allowedOperators = copyMap(values); }
        public Map<String, Set<String>> getAllowedFunctions() { return allowedFunctions; }
        public void setAllowedFunctions(Map<String, Set<String>> values) { allowedFunctions = copyMap(values); }
        public Set<String> getReadableContextTypes() { return readableContextTypes; }
        public void setReadableContextTypes(Set<String> values) { readableContextTypes = copySet(values); }
        public Set<String> getWritableContextTypes() { return writableContextTypes; }
        public void setWritableContextTypes(Set<String> values) { writableContextTypes = copySet(values); }
        public Map<String, String> getAttributes() { return attributes; }
        public void setAttributes(Map<String, String> values) {
            attributes = values == null ? new LinkedHashMap<>() : new LinkedHashMap<>(values);
        }

        private static Set<String> copySet(Set<String> values) {
            return values == null ? new LinkedHashSet<>() : new LinkedHashSet<>(values);
        }

        private static Map<String, Set<String>> copyMap(Map<String, Set<String>> values) {
            Map<String, Set<String>> copy = new LinkedHashMap<>();
            if (values != null) {
                values.forEach((key, value) -> copy.put(key, copySet(value)));
            }
            return copy;
        }
    }
}
