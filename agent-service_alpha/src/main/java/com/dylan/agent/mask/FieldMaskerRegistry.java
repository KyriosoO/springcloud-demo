package com.dylan.agent.mask;

import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

import org.springframework.stereotype.Component;

import com.dylan.agent.model.MaskType;

/**
 * 脱敏器注册中心，启动时校验所有 MaskType 已覆盖。
 */
@Component
public class FieldMaskerRegistry {

    private final Map<MaskType, FieldMasker> maskers;

    public FieldMaskerRegistry(List<FieldMasker> maskerList) {
        Map<MaskType, FieldMasker> map = new EnumMap<>(MaskType.class);
        for (FieldMasker m : maskerList) {
            if (map.put(m.type(), m) != null) {
                throw new IllegalStateException("Duplicate FieldMasker type: " + m.type());
            }
        }
        Set<MaskType> missing = java.util.EnumSet.allOf(MaskType.class);
        missing.removeAll(map.keySet());
        if (!missing.isEmpty()) {
            throw new IllegalStateException("Missing FieldMasker implementations for: " + missing);
        }
        this.maskers = Map.copyOf(map);
    }

    /** 按 MaskType 查找对应的脱敏器并执行脱敏。 */
    public Object mask(MaskType type, Object value) {
        FieldMasker masker = maskers.get(type);
        if (masker == null) {
            throw new IllegalArgumentException("Unknown MaskType: " + type);
        }
        return masker.mask(value);
    }
}
