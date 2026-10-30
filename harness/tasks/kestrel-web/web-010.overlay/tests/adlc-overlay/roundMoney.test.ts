import { describe, expect, it } from 'vitest';
import { formatMoney, parseMoneyInput, roundMoney, sumMoney } from '../../src/lib/money';

// ADLC harness overlay for web-010: halves round away from zero at two decimals.
describe('roundMoney half away from zero', () => {
  it.each([
    [1.005, 1.01],
    [-2.505, -2.51],
    [0.005, 0.01],
    [-0.005, -0.01],
    [10.125, 10.13],
    [-10.125, -10.13],
    [1.255, 1.26],
    [2.675, 2.68],
  ])('roundMoney(%s) = %s', (input, expected) => {
    expect(roundMoney(input)).toBe(expected);
  });

  it('leaves non-halves and whole values alone', () => {
    expect(roundMoney(10.124)).toBe(10.12);
    expect(roundMoney(10.126)).toBe(10.13);
    expect(roundMoney(-1.234)).toBe(-1.23);
    expect(roundMoney(19.99)).toBe(19.99);
    expect(roundMoney(42)).toBe(42);
    expect(roundMoney(0)).toBe(0);
  });

  it('flows through the callers', () => {
    expect(sumMoney([1.0, 0.005])).toBe(1.01);
    expect(parseMoneyInput('1.005')).toBe(1.01);
    expect(parseMoneyInput('-2.505')).toBe(-2.51);
    expect(formatMoney(1.005, 'USD')).toBe('$1.01');
  });
});
