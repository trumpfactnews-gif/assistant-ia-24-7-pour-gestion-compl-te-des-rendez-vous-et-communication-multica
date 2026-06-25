/**
 * Client HTTP de l'API Sentinelle.
 *
 * Sans dépendance React Native : s'appuie sur `fetch` et `AbortController`
 * (disponibles dans RN et Node 18+), ce qui le rend testable hors application.
 */

import type {
  CommunityStats,
  HealthStatus,
  NumberReputation,
  ReportInput,
  ReportResult,
  UrlCheck,
  Verdict,
} from './types';

export class SentinelleApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string = 'error',
  ) {
    super(message);
    this.name = 'SentinelleApiError';
  }
}

export interface ClientOptions {
  baseUrl: string;
  apiKey?: string;
  /** Délai max d'une requête (ms). */
  timeoutMs?: number;
}

interface ApiErrorBody {
  error?: { code?: string; message?: string };
}

export class SentinelleClient {
  private readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly timeoutMs: number;

  constructor(options: ClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, '');
    this.apiKey = options.apiKey;
    this.timeoutMs = options.timeoutMs ?? 8000;
  }

  // -- Endpoints --------------------------------------------------------

  /** Analyse un message et renvoie un verdict de fraude. */
  analyze(message: string, sender?: string, lang?: 'fr' | 'en'): Promise<Verdict> {
    return this.post<Verdict>('/api/v1/analyze', { message, sender, lang });
  }

  /** Signale un numéro ou un domaine frauduleux. */
  report(input: ReportInput): Promise<ReportResult> {
    return this.post<ReportResult>('/api/v1/report', {
      type: input.type,
      value: input.value,
      category: input.category,
      reporter_id: input.reporterId,
      message: input.message,
    });
  }

  /** Réputation communautaire d'un numéro. */
  checkNumber(number: string): Promise<NumberReputation> {
    const qs = `?number=${encodeURIComponent(number)}`;
    return this.get<NumberReputation>(`/api/v1/check-number${qs}`);
  }

  /** Analyse anti-hameçonnage d'une URL. */
  checkUrl(url: string): Promise<UrlCheck> {
    return this.post<UrlCheck>('/api/v1/check-url', { url });
  }

  /** Statistiques communautaires. */
  stats(): Promise<CommunityStats> {
    return this.get<CommunityStats>('/api/v1/stats');
  }

  /** Sonde de santé du service. */
  health(): Promise<HealthStatus> {
    return this.get<HealthStatus>('/health');
  }

  // -- Internes ---------------------------------------------------------

  private headers(): Record<string, string> {
    const h: Record<string, string> = { 'Content-Type': 'application/json' };
    if (this.apiKey) {
      h['X-API-Key'] = this.apiKey;
    }
    return h;
  }

  private get<T>(path: string): Promise<T> {
    return this.request<T>('GET', path);
  }

  private post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>('POST', path, body);
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers: this.headers(),
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
      });
    } catch (err) {
      const aborted = err instanceof Error && err.name === 'AbortError';
      throw new SentinelleApiError(
        aborted ? 'Délai dépassé. Vérifiez votre connexion.' : 'Réseau indisponible.',
        0,
        aborted ? 'timeout' : 'network_error',
      );
    } finally {
      clearTimeout(timer);
    }

    const text = await res.text();
    const data = text ? (JSON.parse(text) as unknown) : null;

    if (!res.ok) {
      const errBody = data as ApiErrorBody | null;
      throw new SentinelleApiError(
        errBody?.error?.message ?? `Erreur ${res.status}`,
        res.status,
        errBody?.error?.code ?? 'error',
      );
    }
    return data as T;
  }
}
