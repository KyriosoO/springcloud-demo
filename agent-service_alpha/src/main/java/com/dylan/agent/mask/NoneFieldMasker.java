package com.dylan.agent.mask;

import org.springframework.stereotype.Component;

import com.dylan.agent.model.MaskType;

/** 空脱敏器：原样返回值，不做任何处理。 */
@Component
public class NoneFieldMasker implements FieldMasker {
    @Override
    public MaskType type() { return MaskType.NONE; }

    @Override
    public Object mask(Object value) { return value; }
}
