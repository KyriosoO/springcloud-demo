package com.dylan.agent.mask;

import org.springframework.stereotype.Component;

import com.dylan.agent.model.MaskType;

/** 地址脱敏器：保留前 6 个字符（如长度不足则显示 ***）。 */
@Component
public class AddressFieldMasker implements FieldMasker {
    @Override
    public MaskType type() { return MaskType.ADDRESS; }

    @Override
    public Object mask(Object value) {
        if (value == null) return null;
        String s = value.toString();
        if (s.isEmpty()) return s;
        if (s.length() > 6) {
            return s.substring(0, 6) + "***";
        }
        return "***";
    }
}
