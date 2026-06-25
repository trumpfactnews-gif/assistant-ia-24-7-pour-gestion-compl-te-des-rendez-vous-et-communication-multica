/**
 * Normalisation/masquage de numéros côté client (logique pure).
 * Aligné sur le backend (E.164 nord-américain, best effort).
 */

export function normalizePhone(raw: string, defaultCountryCode = '1'): string {
  if (!raw) return '';
  const cleaned = raw.trim().replace(/[^\d+]/g, '');
  if (cleaned.startsWith('+')) return cleaned;
  const digits = cleaned.replace(/^\++/, '');
  if (digits.length === 10) return `+${defaultCountryCode}${digits}`;
  if (digits.length === 11 && digits.startsWith(defaultCountryCode)) return `+${digits}`;
  return digits;
}

export function maskPhone(raw: string): string {
  const n = normalizePhone(raw);
  if (!n || n.length < 7) return '***';
  return `${n.slice(0, 5)}***${n.slice(-4)}`;
}

/** Heuristique simple : le « sender » ressemble-t-il à un numéro (vs un nom court) ? */
export function looksLikePhone(sender: string): boolean {
  return /\d{5,}/.test(sender.replace(/[^\d]/g, ''));
}
