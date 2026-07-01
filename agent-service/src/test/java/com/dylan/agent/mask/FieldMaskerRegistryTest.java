package com.dylan.agent.mask;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.model.MaskType;

@DisplayName("FieldMaskerRegistry")
class FieldMaskerRegistryTest {

    private FieldMaskerRegistry registry;

    @BeforeEach
    void setUp() {
        registry = new FieldMaskerRegistry(List.of(
                new NoneFieldMasker(),
                new IdCardFieldMasker(),
                new MobileFieldMasker(),
                new EmailFieldMasker(),
                new AddressFieldMasker()
        ));
    }

    @Nested
    @DisplayName("五种 MaskType 均已注册")
    class AllMaskersRegistered {

        @Test
        @DisplayName("NONE 可执行")
        void shouldMaskNone() {
            Object result = registry.mask(MaskType.NONE, "test");
            assertThat(result).isEqualTo("test");
        }

        @Test
        @DisplayName("ID_CARD 保留前6后4")
        void shouldMaskIdCard() {
            Object result = registry.mask(MaskType.ID_CARD, "110101199001010011");
            assertThat(result).isEqualTo("110101********0011");
        }

        @Test
        @DisplayName("MOBILE 保留前3后4")
        void shouldMaskMobile() {
            Object result = registry.mask(MaskType.MOBILE, "13812345678");
            assertThat(result).isEqualTo("138****5678");
        }

        @Test
        @DisplayName("EMAIL 保留首字符")
        void shouldMaskEmail() {
            Object result = registry.mask(MaskType.EMAIL, "zhangsan@example.com");
            assertThat(result).isEqualTo("z***@example.com");
        }

        @Test
        @DisplayName("ADDRESS 保留前6字符")
        void shouldMaskAddress() {
            Object result = registry.mask(MaskType.ADDRESS, "北京市海淀区中关村大道100号");
            assertThat(result).isEqualTo("北京市海淀区***");
        }
    }

    @Nested
    @DisplayName("重复 MaskType 启动失败")
    class DuplicateRejection {

        @Test
        @DisplayName("重复注册 NONE 抛异常")
        void shouldRejectDuplicateMasker() {
            assertThatThrownBy(() -> new FieldMaskerRegistry(List.of(
                    new NoneFieldMasker(), new NoneFieldMasker())))
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("Duplicate");
        }
    }

    @Nested
    @DisplayName("脱敏异常不回退原值")
    class MaskingSafety {

        @Test
        @DisplayName("身份证号过长/正常格式")
        void shouldMaskNormalIdCard() {
            // 18位身份证
            Object result = registry.mask(MaskType.ID_CARD, "110101199001010011");
            assertThat(result).isNotEqualTo("110101199001010011"); // 不是原值
            assertThat(result.toString()).startsWith("110101");
        }

        @Test
        @DisplayName("过短身份证号脱敏为 ***")
        void shouldMaskShortIdCard() {
            Object result = registry.mask(MaskType.ID_CARD, "123456");
            assertThat(result).isEqualTo("***");
        }

        @Test
        @DisplayName("过短手机号脱敏为 ***")
        void shouldMaskShortMobile() {
            Object result = registry.mask(MaskType.MOBILE, "12345");
            assertThat(result).isEqualTo("***");
        }

        @Test
        @DisplayName("无效邮箱脱敏为 ***")
        void shouldMaskInvalidEmail() {
            Object result = registry.mask(MaskType.EMAIL, "no-at-sign");
            assertThat(result).isEqualTo("***");
        }

        @Test
        @DisplayName("过短地址脱敏为 ***")
        void shouldMaskShortAddress() {
            Object result = registry.mask(MaskType.ADDRESS, "上海市");
            assertThat(result).isEqualTo("***");
        }

        @Test
        @DisplayName("null 保持 null")
        void shouldKeepNull() {
            Object result = registry.mask(MaskType.MOBILE, null);
            assertThat(result).isNull();
        }

        @Test
        @DisplayName("空字符串保持空字符串")
        void shouldKeepEmpty() {
            Object result = registry.mask(MaskType.MOBILE, "");
            assertThat(result).isEqualTo("");
        }
    }
}
