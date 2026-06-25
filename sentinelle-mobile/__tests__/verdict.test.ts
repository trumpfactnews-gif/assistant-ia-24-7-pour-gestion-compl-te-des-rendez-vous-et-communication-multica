import { levelFromScore, levelStyle, pickLang, shouldAlert } from '../src/utils/verdict';
import type { Bilingual } from '../src/api/types';

describe('verdict helpers', () => {
  it('maps scores to the same levels as the backend', () => {
    expect(levelFromScore(0)).toBe('safe');
    expect(levelFromScore(24)).toBe('safe');
    expect(levelFromScore(25)).toBe('caution');
    expect(levelFromScore(50)).toBe('suspicious');
    expect(levelFromScore(75)).toBe('fraud');
    expect(levelFromScore(100)).toBe('fraud');
  });

  it('alerts only on suspicious or fraud', () => {
    expect(shouldAlert('safe')).toBe(false);
    expect(shouldAlert('caution')).toBe(false);
    expect(shouldAlert('suspicious')).toBe(true);
    expect(shouldAlert('fraud')).toBe(true);
  });

  it('provides a distinct style per level', () => {
    expect(levelStyle('fraud').color).not.toBe(levelStyle('safe').color);
    expect(levelStyle('fraud').emoji).toBeTruthy();
  });

  it('picks the requested language with fallback', () => {
    const b: Bilingual = { fr: 'Bonjour', en: 'Hello' };
    expect(pickLang(b, 'fr')).toBe('Bonjour');
    expect(pickLang(b, 'en')).toBe('Hello');
    expect(pickLang({ fr: '', en: 'Hello' }, 'fr')).toBe('Hello');
  });
});
