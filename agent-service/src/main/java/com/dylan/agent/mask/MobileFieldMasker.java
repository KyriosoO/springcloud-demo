package com.dylan.agent.mask;

import org.springframework.stereotype.Component;

import com.dylan.agent.model.MaskType;

/** 手机号脱敏器：保留前 3 后 4 位，中间用星号替换。 */
@Component
public class MobileFieldMasker implements FieldMasker {
    @Override
    public MaskType type() { return MaskType.MOBILE; }

    @Override
    public Object mask(Object value) {
        if (value == null) return null;
        String s = value.toString();
        if (s.isEmpty()) return s;
        if (s.length() >= 7) {
            return s.substring(0, 3) + "****" + s.substring(s.length() - 4);
        }
        return "***";
    }
}
