package com.kestrel.booking;

import static org.assertj.core.api.Assertions.assertThat;

import com.kestrel.booking.domain.Carrier;
import com.kestrel.booking.domain.Shipment;
import com.kestrel.booking.repo.CarrierRepository;
import com.kestrel.booking.repo.ShipmentRepository;
import com.kestrel.booking.support.Fixtures;
import jakarta.persistence.EntityManager;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.FetchType;
import java.lang.reflect.Field;
import java.math.BigDecimal;
import java.util.Arrays;
import org.hibernate.Hibernate;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.test.context.ActiveProfiles;

/** ADLC harness overlay for svc-010: Shipment declares a lazy many-to-one to Carrier. */
@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@ActiveProfiles("test")
class AdlcOverlayCarrierRelationTest {

    @Autowired
    private ShipmentRepository shipments;

    @Autowired
    private CarrierRepository carriers;

    @Autowired
    private EntityManager em;

    private static Field carrierField() {
        return Arrays.stream(Shipment.class.getDeclaredFields())
                .filter(f -> f.getType() == Carrier.class)
                .findFirst()
                .orElse(null);
    }

    @Test
    void shipmentDeclaresALazyManyToOneJoinedOnCarrierId() {
        Field field = carrierField();

        assertThat(field).as("a Carrier-typed field on Shipment").isNotNull();
        ManyToOne many = field.getAnnotation(ManyToOne.class);
        assertThat(many).as("@ManyToOne").isNotNull();
        assertThat(many.fetch()).isEqualTo(FetchType.LAZY);
        JoinColumn join = field.getAnnotation(JoinColumn.class);
        assertThat(join).as("@JoinColumn").isNotNull();
        assertThat(join.name()).isEqualTo("carrier_id");
    }

    @Test
    void relationResolvesTheCarrierAndCarrierIdStillWorks() throws Exception {
        Field field = carrierField();
        assertThat(field).as("a Carrier-typed field on Shipment").isNotNull();
        field.setAccessible(true);
        Carrier nsl = carriers.findByCodeIgnoreCase("NSL").orElseThrow();
        Shipment saved = shipments.saveAndFlush(new Shipment("KB-OVERLAY0001", "NLRTM", "DEHAM",
                nsl.getId(), new BigDecimal("100"), Fixtures.T0.plusSeconds(3600), Fixtures.T0));
        em.clear();

        Shipment loaded = shipments.findById(saved.getId()).orElseThrow();

        assertThat(loaded.getCarrierId()).isEqualTo(nsl.getId());
        Object related = field.get(loaded);
        assertThat(related).isNotNull();
        assertThat(Hibernate.isInitialized(related)).as("lazy").isFalse();
        assertThat(((Carrier) related).getCode()).isEqualTo("NSL");
    }
}
