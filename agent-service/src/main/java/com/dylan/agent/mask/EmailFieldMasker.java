package com.dylan.agent.mask;

import org.springframework.stereotype.Component;

import com.dylan.agent.model.MaskType;

/** 邮箱脱敏器：保留首字符和域名部分，中间替换为 ***。 */
@Component
public class EmailFieldMasker implements FieldMasker {
    @Override
    public MaskType type() { return MaskType.EMAIL; }

    @Override
    public Object mask(Object value) {
        if (value == null) return null;
        String s = value.toString();
        if (s.isEmpty()) return s;
        int at = s.indexOf('@');
        if (at > 0 && at < s.length() - 1) {
            return s.charAt(0) + "***@" + s.substring(at + 1);
        }
        return "***";
    }
}
