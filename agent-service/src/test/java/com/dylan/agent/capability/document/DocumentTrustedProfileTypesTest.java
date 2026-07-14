package com.dylan.agent.capability.document;

import com.dylan.agent.capability.document.profile.DocumentPlanningProfileProjection;
import com.dylan.agent.capability.document.profile.DocumentProfileSelection;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Modifier;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentTrustedProfileTypesTest {
    @Test
    void trustedSelectionProjectionAndBindingHaveNoPublicConstructor() {
        assertThat(DocumentProfileSelection.class.getDeclaredConstructors())
                .allMatch(constructor -> !Modifier.isPublic(constructor.getModifiers()));
        assertThat(DocumentPlanningProfileProjection.class.getDeclaredConstructors())
                .allMatch(constructor -> !Modifier.isPublic(constructor.getModifiers()));
        assertThat(DocumentProfileBinding.class.getDeclaredConstructors())
                .allMatch(constructor -> !Modifier.isPublic(constructor.getModifiers()));
        assertThat(DocumentExecutionProfileProjection.class.getDeclaredConstructors())
                .allMatch(constructor -> !Modifier.isPublic(constructor.getModifiers()));
    }
}
