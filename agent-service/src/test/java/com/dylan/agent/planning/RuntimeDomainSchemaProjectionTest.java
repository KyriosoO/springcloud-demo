package com.dylan.agent.planning;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.api.runtime.RuntimeDomainSchema;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

@DisplayName("RuntimeDomainSchemaProjection")
class RuntimeDomainSchemaProjectionTest {

    private RuntimeDomainSchemaProjection projection;

    @BeforeEach
    void setUp() {
        projection = new RuntimeDomainSchemaProjection(
                DomainMetadataTestSupport.agentProperties(),
                DomainMetadataTestSupport.catalogView());
    }

    @Nested
    @DisplayName("Schema 构造")
    class SchemaConstruction {

        @Test
        @DisplayName("字段来自 D04 Canonical Catalog")
        void shouldContainFieldsFromD04Catalog() {
            RuntimeDomainSchema schema = projection.create("employee");

            var names = schema.getFields().stream().map(f -> f.getName()).toList();
            assertThat(names).contains(
                    "chineseName", "memberNo", "position",
                    "contactAddress", "idCardNo", "phoneNo", "email");
        }

        @Test
        @DisplayName("不向 Runtime 暴露角色")
        void shouldNotExposeRoles() {
            RuntimeDomainSchema schema = projection.create("employee");

            String schemaJson = schema.toString();
            assertThat(schemaJson).doesNotContain("agent:admin");
            assertThat(schemaJson).doesNotContain("filterRoles");
            assertThat(schemaJson).doesNotContain("displayRoles");
        }

        @Test
        @DisplayName("不向 Runtime 暴露 mask")
        void shouldNotExposeMask() {
            RuntimeDomainSchema schema = projection.create("employee");

            String schemaJson = schema.toString();
            assertThat(schemaJson).doesNotContain("ID_CARD");
            assertThat(schemaJson).doesNotContain("mask");
        }

        @Test
        @DisplayName("包含 query 限制参数")
        void shouldIncludeQueryLimits() {
            RuntimeDomainSchema schema = projection.create("employee");

            assertThat(schema.getMaxFilters()).isEqualTo(5);
            assertThat(schema.getDefaultSize()).isEqualTo(20);
            assertThat(schema.getMaxSize()).isEqualTo(100);
        }
    }
}
