package com.dylan.agent.mask;

import org.springframework.stereotype.Component;

import com.dylan.agent.model.MaskType;

/** 身份证号脱敏器：保留前 6 后 4 位，中间用星号替换。 */
@Component
public class IdCardFieldMasker implements FieldMasker {
    @Override
    public MaskType type() { return MaskType.ID_CARD; }

    @Override
    public Object mask(Object value) {
        if (value == null) return null;
        String s = value.toString();
        if (s.isEmpty()) return s;
        if (s.length() >= 10) {
            return s.substring(0, 6) + "********" + s.substring(s.length() - 4);
        }
        return "***";
    }
}
