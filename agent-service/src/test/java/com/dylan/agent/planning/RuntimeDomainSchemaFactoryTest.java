package com.dylan.agent.planning;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.runtime.RuntimeDomainSchema;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.model.MaskType;

@DisplayName("RuntimeDomainSchemaFactory")
class RuntimeDomainSchemaFactoryTest {

    private RuntimeDomainSchemaFactory factory;

    @BeforeEach
    void setUp() {
        AgentProperties p = new AgentProperties();
        AgentProperties.QueryProperties q = new AgentProperties.QueryProperties();
        q.setMaxFilters(5); q.setDefaultSize(20); q.setMaxSize(100); q.setMaxResultWindow(10000);
        p.setQuery(q);

        AgentProperties.DomainProperties emp = new AgentProperties.DomainProperties();
        emp.setAliases(List.of("员工", "employee"));
        emp.setAccessRoles(Set.of("agent:viewer", "agent:admin"));
        emp.setDefaultSelectFields(List.of("chineseName", "memberNo", "position"));

        Map<String, AgentProperties.FieldProperties> fields = new java.util.HashMap<>();
        for (String name : java.util.List.of("chineseName", "memberNo", "position",
                "contactAddress", "idCardNo", "phoneNo", "email")) {
            AgentProperties.FieldProperties fp = new AgentProperties.FieldProperties();
            fp.setAliases(List.of(name + "_alias"));
            fp.setType(com.dylan.agent.api.enums.AgentFieldType.STRING);
            fp.setOperators(Set.of(AgentOperator.EQ, AgentOperator.CONTAINS, AgentOperator.STARTS_WITH, AgentOperator.IN));
            fp.setFilterRoles(Set.of("agent:admin"));
            fp.setDisplayRoles(Set.of("agent:admin"));
            fp.setMask(MaskType.NONE);
            fields.put(name, fp);
        }
        emp.setFields(fields);
        p.setDomains(Map.of("employee", emp));

        factory = new RuntimeDomainSchemaFactory(p, null);
    }

    @Nested
    @DisplayName("Schema 构造")
    class SchemaConstruction {

        @Test
        @DisplayName("包含七个字段")
        void shouldContainSevenFields() {
            RuntimeDomainSchema schema = factory.create("employee");
            assertThat(schema.getFields()).hasSize(7);
            // HashMap 不保证顺序，只验证包含所有字段
            var names = schema.getFields().stream().map(f -> f.getName()).toList();
            assertThat(names).containsExactlyInAnyOrder(
                    "chineseName", "memberNo", "position",
                    "contactAddress", "idCardNo", "phoneNo", "email");
        }

        @Test
        @DisplayName("不向 Runtime 暴露角色")
        void shouldNotExposeRoles() {
            RuntimeDomainSchema schema = factory.create("employee");
            // domainSchema 只有 filed name, aliases, operators — 不含 roles 和 mask
            String schemaJson = schema.toString();
            assertThat(schemaJson).doesNotContain("agent:admin");
            assertThat(schemaJson).doesNotContain("filterRoles");
            assertThat(schemaJson).doesNotContain("displayRoles");
        }

        @Test
        @DisplayName("不向 Runtime 暴露 mask")
        void shouldNotExposeMask() {
            RuntimeDomainSchema schema = factory.create("employee");
            String schemaJson = schema.toString();
            assertThat(schemaJson).doesNotContain("NONE");
            assertThat(schemaJson).doesNotContain("mask");
        }

        @Test
        @DisplayName("包含 query 限制参数")
        void shouldIncludeQueryLimits() {
            RuntimeDomainSchema schema = factory.create("employee");
            assertThat(schema.getMaxFilters()).isEqualTo(5);
            assertThat(schema.getDefaultSize()).isEqualTo(20);
            assertThat(schema.getMaxSize()).isEqualTo(100);
        }
    }
}
