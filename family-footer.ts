/**
 * Fun with Quantum family footer column, from the shared manifest
 * (family/family.json in JanLahmann/Fun-with-Quantum).
 *
 * Fetched at build time (Fun-with-Quantum fires repository_dispatch at this repo when the roster
 * changes); falls back to the vendored ./fwq-family.json — which an automated PR keeps fresh — so
 * an offline build never breaks. Never hand-edit the vendored copy.
 */
import vendored from './fwq-family.json';

interface Member { id: string; name: string; url: string; short?: string; footer: boolean }
interface Manifest { version: number; updated: string; brand: { id: string; name: string; footer_lead: string }; members: Member[] }

const MANIFEST_URL = 'https://raw.githubusercontent.com/JanLahmann/Fun-with-Quantum/master/family/family.json';

async function loadFamily(): Promise<Manifest> {
  const fallback = vendored as Manifest;
  if (process.env.FWQ_FAMILY_OFFLINE === '1') return fallback;
  try {
    // ?t= busts the ~5-minute raw.githubusercontent CDN cache so a dispatched rebuild sees the new roster.
    const res = await fetch(process.env.FWQ_FAMILY_URL ?? `${MANIFEST_URL}?t=${Date.now()}`, { signal: AbortSignal.timeout(8000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = (await res.json()) as Manifest;
    if (json.version !== 1 || !Array.isArray(json.members)) throw new Error('unexpected manifest shape');
    console.log(`[family] manifest fetched (updated ${json.updated})`);
    return json;
  } catch (err) {
    console.warn(`[family] live manifest unavailable (${(err as Error).message}); using vendored copy (updated ${fallback.updated})`);
    return fallback;
  }
}

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');

/** A Docusaurus footer column: every visible member except this site, name + short description. */
export async function familyFooterColumn(selfId: string) {
  const m = await loadFamily();
  return {
    title: `${m.brand.name} family`,
    items: m.members
      .filter((x) => x.footer && x.id !== selfId)
      .map((x) => ({
        html: `<a class="footer__link-item fwq-member" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" data-umami-event="family-footer" data-umami-event-to="${esc(x.id)}">${esc(x.name)}${x.short ? `<small>${esc(x.short)}</small>` : ''}</a>`,
      })),
  };
}
