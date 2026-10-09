/**
 * The "Play it as a game" box (components/PlayBox): pages whose topic one of the Fun with Quantum
 * games plays out, and those games. Only games with a public page on fun-with-quantum.org/play/
 * belong here; the portal keeps its unpublished games under /preview/, which must not be linked.
 *
 * Keys are the page's path under docs/ (the same for every locale).
 */

export type PlayGameId = 'coin' | 'ghz' | 'chsh' | 'ghzReal' | 'sat';

export type PlayGame = {
  /** Page on fun-with-quantum.org. */
  path: string;
  /** true: the game itself plays on that page; false: the page launches a Jupyter notebook. */
  browser: boolean;
  /** doQumentation locales the page exists in besides English, at /<locale><path>. */
  locales: string[];
};

export const PLAY_GAMES: Record<PlayGameId, PlayGame> = {
  coin: {path: '/play/quantum-coin-game/', browser: true, locales: ['de', 'ja', 'es', 'uk', 'it', 'fr']},
  ghz: {path: '/play/ghz-game/', browser: true, locales: []},
  chsh: {path: '/play/chsh-game/', browser: true, locales: []},
  ghzReal: {path: '/play/ghz-real-devices/', browser: false, locales: []},
  sat: {path: '/play/3sat-grover/', browser: false, locales: []},
};

export const PLAY_PAGES: Record<string, PlayGameId[]> = {
  // superposition and interference
  'learning/modules/quantum-mechanics/superposition-with-qiskit.mdx': ['coin'],
  'learning/courses/basics-of-quantum-information/single-systems/quantum-information.mdx': ['coin'],
  'tutorials/hello-world.mdx': ['coin'],
  'learning/courses/use-a-qc-today/build-and-run-your-first-quantum-program.mdx': ['coin'],
  // Bell tests and nonlocal games
  'tutorials/chsh-inequality.mdx': ['chsh'],
  'learning/courses/basics-of-quantum-information/entanglement-in-action/chsh-game.mdx': ['chsh', 'ghz'],
  'learning/courses/basics-of-quantum-information/entanglement-in-action/qiskit-implementation.mdx': ['chsh'],
  'learning/modules/quantum-mechanics/bells-inequality-with-qiskit.mdx': ['chsh'],
  // GHZ states, and GHZ circuits on noisy hardware
  'learning/courses/basics-of-quantum-information/multiple-systems/quantum-information.mdx': ['ghz'],
  'learning/courses/utility-scale-quantum-computing/utility-iii.mdx': ['ghzReal'],
  'learning/courses/utility-scale-quantum-computing/quantum-circuit-optimization.mdx': ['ghzReal'],
  // Grover's search
  'tutorials/grovers-algorithm.mdx': ['sat'],
  'learning/modules/computer-science/grovers.mdx': ['sat'],
  'learning/courses/utility-scale-quantum-computing/grovers-algorithm.mdx': ['sat'],
  'learning/courses/fundamentals-of-quantum-algorithms/grover-algorithm/introduction.mdx': ['sat'],
};

const PORTAL = 'https://fun-with-quantum.org';
// Fun with Quantum family campaign tags, so the portal's analytics can tell these visits apart.
const UTM = 'utm_source=doqumentation&utm_medium=referral&utm_campaign=play-box';

export const PORTAL_HOME = `${PORTAL}/?${UTM}`;

/** The game's URL for a doQumentation locale, and whether it is in that language. */
export function playGameUrl(game: PlayGame, locale: string): {href: string; localized: boolean} {
  const localized = locale === 'en' || game.locales.includes(locale);
  const prefix = locale !== 'en' && game.locales.includes(locale) ? `/${locale}` : '';
  return {href: `${PORTAL}${prefix}${game.path}?${UTM}`, localized};
}
