/**
 * Types du contrat d'API Sentinelle.
 * Miroir fidèle des réponses du backend (`sentinelle-backend`).
 */

export type RiskLevel = 'safe' | 'caution' | 'suspicious' | 'fraud';
export type Lang = 'fr' | 'en';

export interface Bilingual {
  fr: string;
  en: string;
}

export interface Signal {
  code: string;
  category: string;
  label: Bilingual;
  evidence: string;
}

export interface UrlReason {
  code: string;
  fr: string;
  en: string;
}

export interface UrlFinding {
  url: string;
  host: string;
  registrable_domain: string;
  is_official: boolean;
  score: number;
  reasons: UrlReason[];
}

export interface VerdictComponents {
  heuristics: number;
  url: number;
  ml: number | null;
  community: number;
}

/** Réponse de `POST /api/v1/analyze`. */
export interface Verdict {
  risk_score: number;
  level: RiskLevel;
  level_label: Bilingual;
  category: string;
  category_label: Bilingual;
  is_fraud: boolean;
  language: Lang;
  version: string;
  components: VerdictComponents;
  signals: Signal[];
  analyzed_urls: UrlFinding[];
  explanation: Bilingual;
  recommended_action: Bilingual;
}

/** Réponse de `POST /api/v1/report`. */
export interface ReportResult {
  target_type: string;
  target_display: string;
  category: string | null;
  report_count: number;
  blocked: boolean;
  block_threshold: number;
}

/** Réponse de `GET /api/v1/check-number`. */
export interface NumberReputation {
  blocked: boolean;
  report_count: number;
  category: string | null;
  display: string;
}

/** Réponse de `POST /api/v1/check-url`. */
export interface UrlCheck extends UrlFinding {
  community_blocked: boolean;
}

export interface CommunityStats {
  total_reports: number;
  blocked_numbers: number;
  tracked_numbers: number;
  blocked_domains: number;
  tracked_domains: number;
  block_threshold: number;
}

export interface HealthStatus {
  status: string;
  service: string;
  ml_available: boolean;
}

export type ReportType = 'number' | 'domain';

export interface ReportInput {
  type: ReportType;
  value: string;
  category?: string;
  reporterId?: string;
  message?: string;
}
