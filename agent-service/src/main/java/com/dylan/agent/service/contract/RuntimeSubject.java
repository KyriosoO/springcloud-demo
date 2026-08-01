package com.dylan.agent.service.contract;

public record RuntimeSubject(String id, String type) {

    public RuntimeSubject {
        if (id == null || id.isBlank() || !"user".equals(type)) {
            throw new IllegalArgumentException("agent.runtime-subject-invalid");
        }
    }
}
