import { offlineAnalyze } from '../src/detection/offline';

describe('offlineAnalyze', () => {
  it('flags a bank phishing message as fraud', () => {
    const v = offlineAnalyze(
      'Desjardins: votre compte est bloqué. Vérifiez: http://desjardins-securite.xyz/login',
    );
    expect(v.is_fraud).toBe(true);
    expect(v.risk_score).toBeGreaterThanOrEqual(50);
    expect(v.category).toBe('bank_fraud');
    expect(v.analyzed_urls.some((u) => !u.is_official)).toBe(true);
  });

  it('treats a benign message as safe', () => {
    const v = offlineAnalyze('Salut! On se voit à 19h au resto ce soir?');
    expect(v.level).toBe('safe');
    expect(v.is_fraud).toBe(false);
  });

  it('does not flag an official domain link', () => {
    const v = offlineAnalyze('Votre relevé est prêt sur https://www.desjardins.com');
    const dj = v.analyzed_urls.find((u) => u.registrable_domain === 'desjardins.com');
    expect(dj?.is_official).toBe(true);
  });

  it('detects a gift-card scam strongly', () => {
    const v = offlineAnalyze('Payez votre amende en carte cadeau Google Play immédiatement.');
    expect(v.risk_score).toBeGreaterThanOrEqual(70);
  });

  it('marks the verdict as offline', () => {
    const v = offlineAnalyze('test');
    expect(v.version).toBe('offline');
    expect(v.explanation.fr).toContain('hors ligne');
  });
});
