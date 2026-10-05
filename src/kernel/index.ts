/**
 * Python run on every Jupyter kernel before the page's cells. The sources are
 * real .py files (bundled as strings by plugins/python-source) so that
 * scripts/check-simulator-mode.py can run doc pages against the exact code the
 * site injects. Keep these functions free of browser state: the check mirrors
 * them in Python.
 */
import saveAccountGuardPy from './save_account_guard.py';
import simulatorPatchPy from './simulator_patch.py';
import pages from './pages.json';

/** A page path matches with or without a locale prefix or trailing slash. */
function pageMatches(path: string, page: string): boolean {
  const p = path.replace(/\/$/, '');
  return p === page || p.endsWith(page);
}

export function isSimulatorExemptPath(path: string): boolean {
  return pages.exempt.some(p => pageMatches(path, p));
}

/** The small fake device a page needs in Simulator Mode, or null. */
export function pageSimulatorDevice(path: string): string | null {
  const hit = Object.entries(pages.device).find(([p]) => pageMatches(path, p));
  return hit ? hit[1] : null;
}

export function saveAccountGuardCode(): string {
  return saveAccountGuardPy;
}

/** device: a qiskit_ibm_runtime.fake_provider class name, or null for the ideal AerSimulator. */
export function simulatorPatchCode(device: string | null, suppressWarnings: boolean): string {
  const safe = (device ?? '').replace(/[^a-zA-Z0-9_]/g, '');
  return `_DQ_DEVICE = ${safe ? `"${safe}"` : 'None'}
_DQ_SUPPRESS_WARNINGS = ${suppressWarnings ? 'True' : 'False'}
${simulatorPatchPy}`;
}
