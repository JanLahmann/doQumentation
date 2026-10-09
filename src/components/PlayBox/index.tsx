/**
 * "Play it as a game": on pages whose topic a Fun with Quantum game plays out
 * (src/config/playGames.ts), a short box at the end of the page linking to that game on
 * fun-with-quantum.org. Clicks report `doQumentation: play box click` (Umami data attributes).
 */
import React from 'react';
import Translate, {translate} from '@docusaurus/Translate';
import {PLAY_GAMES, PLAY_PAGES, PORTAL_HOME, playGameUrl, type PlayGameId} from '../../config/playGames';
import './styles.css';

// Static ids, so `write-translations` finds every string.
function gameText(id: PlayGameId): {title: string; text: string} {
  switch (id) {
    case 'coin':
      return {
        title: translate({id: 'playBox.coin.title', message: 'Quantum Coin Game', description: 'Name of a game on fun-with-quantum.org'}),
        text: translate({id: 'playBox.coin.text', message: 'Try to beat a quantum computer at coin flipping, and find out why it wins every time.', description: 'One-line description of the Quantum Coin Game'}),
      };
    case 'ghz':
      return {
        title: translate({id: 'playBox.ghz.title', message: 'GHZ Game', description: 'Name of a game on fun-with-quantum.org'}),
        text: translate({id: 'playBox.ghz.text', message: 'A team game that no classical strategy wins every round. With entanglement, you always do.', description: 'One-line description of the GHZ Game'}),
      };
    case 'chsh':
      return {
        title: translate({id: 'playBox.chsh.title', message: 'The CHSH Game', description: 'Name of a game on fun-with-quantum.org'}),
        text: translate({id: 'playBox.chsh.text', message: 'The Bell test as a game: no classical team wins more than 75% of the rounds, an entangled team wins 85.4%.', description: 'One-line description of the CHSH Game'}),
      };
    case 'ghzReal':
      return {
        title: translate({id: 'playBox.ghzReal.title', message: 'GHZ on Real Quantum Devices', description: 'Name of a notebook on fun-with-quantum.org'}),
        text: translate({id: 'playBox.ghzReal.text', message: 'Play the GHZ Game on noisy copies of IBM quantum computers, and win back most of the rounds the noise costs you.', description: 'One-line description of the GHZ on Real Quantum Devices notebook'}),
      };
    case 'sat':
      return {
        title: translate({id: 'playBox.sat.title', message: "3-SAT with Grover's Algorithm", description: 'Name of a notebook on fun-with-quantum.org'}),
        text: translate({id: 'playBox.sat.text', message: "Watch Grover's search find the answer to a logic puzzle among N candidates in about √N steps instead of N.", description: "One-line description of the 3-SAT with Grover's Algorithm notebook"}),
      };
  }
}

export default function PlayBox({relPath, locale}: {relPath: string | null; locale: string}): React.JSX.Element | null {
  const ids = relPath ? PLAY_PAGES[relPath] : undefined;
  if (!ids) return null;

  return (
    <aside className="dq-play-box">
      <div className="dq-play-box__heading">
        <Translate id="playBox.heading" description="Heading of the box that links a page to a matching quantum game">
          Play it as a game
        </Translate>
      </div>
      <ul className="dq-play-box__games">
        {ids.map((id) => {
          const game = PLAY_GAMES[id];
          const {href, localized} = playGameUrl(game, locale);
          const {title, text} = gameText(id);
          return (
            <li key={id}>
              <a
                href={href}
                target="_blank"
                rel="noopener"
                className="dq-play-box__link"
                data-umami-event="doQumentation: play box click"
                data-umami-event-game={id}
                data-umami-event-page={relPath ?? ''}
                data-umami-event-locale={locale}
              >
                {title}
              </a>
              <span className="dq-play-box__mode">
                {game.browser ? (
                  <Translate id="playBox.mode.browser" description="Label: the game plays on the linked web page">
                    plays in your browser
                  </Translate>
                ) : (
                  <Translate id="playBox.mode.notebook" description="Label: the linked page opens a Jupyter notebook">
                    Jupyter notebook
                  </Translate>
                )}
                {!localized && (
                  <>
                    {' · '}
                    <Translate id="playBox.inEnglish" description="Label: the linked page is only in English">
                      in English
                    </Translate>
                  </>
                )}
              </span>
              <p className="dq-play-box__text">{text}</p>
            </li>
          );
        })}
      </ul>
      <div className="dq-play-box__from">
        <Translate
          id="playBox.from"
          description="Credit line of the game box; {link} is the project name Fun with Quantum"
          values={{link: <a href={PORTAL_HOME} target="_blank" rel="noopener">Fun with Quantum</a>}}
        >
          {'From {link}, quantum computing taught through games'}
        </Translate>
      </div>
    </aside>
  );
}
