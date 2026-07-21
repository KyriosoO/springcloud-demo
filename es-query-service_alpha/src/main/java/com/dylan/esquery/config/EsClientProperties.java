package com.dylan.esquery.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.ArrayList;
import java.util.List;

@ConfigurationProperties(prefix = "es.clients")
public class EsClientProperties {
    private Endpoint generic = new Endpoint();
    private Endpoint document = new Endpoint();
    public Endpoint getGeneric() { return generic; } public void setGeneric(Endpoint value) { generic = value; }
    public Endpoint getDocument() { return document; } public void setDocument(Endpoint value) { document = value; }
    public void validate() {
        generic.validate("generic"); document.validate("document");
        if (generic.roleRef.equals(document.roleRef)) throw new IllegalStateException("generic/document ES role refs must be distinct");
    }
    public static class Endpoint {
        private List<String> uris = new ArrayList<>();
        private String username;
        private String password;
        private String roleRef;
        public List<String> getUris() { return uris; } public void setUris(List<String> value) { uris = value == null ? new ArrayList<>() : new ArrayList<>(value); }
        public String getUsername() { return username; } public void setUsername(String value) { username = value; }
        public String getPassword() { return password; } public void setPassword(String value) { password = value; }
        public String getRoleRef() { return roleRef; } public void setRoleRef(String value) { roleRef = value; }
        private void validate(String name) {
            if (uris.isEmpty() || uris.stream().anyMatch(value -> value == null || value.isBlank())) throw new IllegalStateException(name + " ES uris required");
            if (roleRef == null || !roleRef.matches("[a-z0-9-]{1,128}")) throw new IllegalStateException(name + " ES role ref invalid");
            if ((username == null || username.isBlank()) != (password == null || password.isBlank())) throw new IllegalStateException(name + " ES credential binding incomplete");
        }
    }
}
