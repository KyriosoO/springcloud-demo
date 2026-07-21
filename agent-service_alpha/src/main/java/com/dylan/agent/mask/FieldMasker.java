package com.dylan.agent.mask;

import com.dylan.agent.model.MaskType;

/**
 * 字段脱敏器接口。
 */
public interface FieldMasker {
    MaskType type();
    Object mask(Object value);
}
