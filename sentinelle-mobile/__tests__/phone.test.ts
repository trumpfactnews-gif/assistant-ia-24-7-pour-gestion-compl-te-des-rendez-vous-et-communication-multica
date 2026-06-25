import { looksLikePhone, maskPhone, normalizePhone } from '../src/utils/phone';

describe('phone helpers', () => {
  it('normalizes North-American numbers to E.164', () => {
    expect(normalizePhone('(514) 555-0199')).toBe('+15145550199');
    expect(normalizePhone('514-555-0199')).toBe('+15145550199');
    expect(normalizePhone('1 514 555 0199')).toBe('+15145550199');
    expect(normalizePhone('+15145550199')).toBe('+15145550199');
  });

  it('masks numbers safely for display', () => {
    expect(maskPhone('(514) 555-0199')).toBe('+1514***0199');
    expect(maskPhone('')).toBe('***');
  });

  it('detects whether a sender looks like a phone number', () => {
    expect(looksLikePhone('+15145550199')).toBe(true);
    expect(looksLikePhone('DESJARDINS')).toBe(false);
  });
});
