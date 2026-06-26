import { SentinelleApiError, SentinelleClient } from '../src/api/client';

describe('SentinelleClient', () => {
  const baseUrl = 'http://test.local';
  let fetchMock: jest.Mock;

  beforeEach(() => {
    fetchMock = jest.fn();
    (globalThis as unknown as { fetch: jest.Mock }).fetch = fetchMock;
  });

  function ok(body: unknown) {
    return Promise.resolve({
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify(body)),
    } as Response);
  }

  it('sends the message to /analyze and returns the verdict', async () => {
    fetchMock.mockReturnValue(ok({ risk_score: 85, level: 'fraud' }));
    const client = new SentinelleClient({ baseUrl });
    const verdict = await client.analyze('coucou', '+15145550199', 'fr');

    expect(verdict.risk_score).toBe(85);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${baseUrl}/api/v1/analyze`);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({
      message: 'coucou',
      sender: '+15145550199',
      lang: 'fr',
    });
  });

  it('adds the X-API-Key header when configured', async () => {
    fetchMock.mockReturnValue(ok({ status: 'ok' }));
    const client = new SentinelleClient({ baseUrl, apiKey: 'secret' });
    await client.health();
    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers['X-API-Key']).toBe('secret');
  });

  it('maps report camelCase fields to the API snake_case body', async () => {
    fetchMock.mockReturnValue(ok({ blocked: false }));
    const client = new SentinelleClient({ baseUrl });
    await client.report({ type: 'number', value: '+1', reporterId: 'dev', category: 'bank_fraud' });
    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      type: 'number',
      value: '+1',
      category: 'bank_fraud',
      reporter_id: 'dev',
      message: undefined,
    });
  });

  it('throws a typed error on non-2xx responses', async () => {
    fetchMock.mockReturnValue(
      Promise.resolve({
        ok: false,
        status: 400,
        text: () =>
          Promise.resolve(JSON.stringify({ error: { code: 'missing_field', message: 'requis' } })),
      } as Response),
    );
    const client = new SentinelleClient({ baseUrl });
    await expect(client.analyze('')).rejects.toMatchObject({
      name: 'SentinelleApiError',
      status: 400,
      code: 'missing_field',
    });
    await expect(client.analyze('')).rejects.toBeInstanceOf(SentinelleApiError);
  });
});
