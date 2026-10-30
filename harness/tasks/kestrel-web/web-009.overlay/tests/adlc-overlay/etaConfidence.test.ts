import { describe, expect, it } from 'vitest';
import { mapShipment } from '../../src/api/mappers';
import { shipmentWire } from '../helpers';

// ADLC harness overlay for web-009: etaConfidence is carried through, absent maps to null.
describe('mapShipment etaConfidence', () => {
  it('carries a present value as etaConfidence', () => {
    const wire = { ...shipmentWire(), eta_confidence: 0.82 };
    expect(mapShipment(wire).etaConfidence).toBe(0.82);
  });

  it('keeps zero and one (falsy/edge values) intact', () => {
    expect(mapShipment({ ...shipmentWire(), eta_confidence: 0 }).etaConfidence).toBe(0);
    expect(mapShipment({ ...shipmentWire(), eta_confidence: 1 }).etaConfidence).toBe(1);
  });

  it('maps an absent value to null', () => {
    const mapped = mapShipment(shipmentWire());
    expect(mapped.etaConfidence).toBeNull();
    expect('etaConfidence' in mapped).toBe(true);
  });

  it('maps an explicit null to null', () => {
    const wire = { ...shipmentWire(), eta_confidence: null };
    expect(mapShipment(wire).etaConfidence).toBeNull();
  });

  it('does not leak the snake_case key', () => {
    const wire = { ...shipmentWire(), eta_confidence: 0.5 };
    expect(Object.keys(mapShipment(wire))).not.toContain('eta_confidence');
  });
});
