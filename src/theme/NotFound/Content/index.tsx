/**
 * Helpful 404 page (swizzled from @docusaurus/theme-classic NotFound/Content).
 *
 * GitHub Pages serves 404.html for any unknown path — including a real page
 * with a trailing slash (/guides/, trailingSlash: false) and a real page whose
 * name is also a folder (GH Pages 301s /x to /x/). On mount we look the path up
 * in Docusaurus' own route table and, if a real page matches (slash stripped,
 * IBM-style /docs/en/… mapped), switch to it with a client-side history.replace:
 * no server round trip, so the GH Pages folder redirect cannot bounce us back.
 * Otherwise: a search box, near matches, and links to the main sections.
 * Works the same on every language subdomain (each build has its own routes).
 */
import React, {useEffect, useMemo, useState, type FormEvent} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import Translate, {translate} from '@docusaurus/Translate';
import {useHistory, useLocation} from '@docusaurus/router';
import Heading from '@theme/Heading';
import routes from '@generated/routes';
import type {Props} from '@theme/NotFound/Content';
import {collectPagePaths, findRedirect, ibmUrlFor, searchTermFromPath, suggestPages, type RouteLike} from './resolve';
import styles from './styles.module.css';

let pageSet: Set<string> | null = null;
const pages = () => (pageSet ??= collectPagePaths(routes as RouteLike[]));

export default function NotFoundContent({className}: Props): React.JSX.Element {
  const location = useLocation();
  const history = useHistory();
  // Client-only state: the static 404.html is rendered for "/404.html", so
  // anything path-specific is filled in after hydration.
  const [state, setState] = useState<{path: string; redirecting: boolean} | null>(null);

  useEffect(() => {
    const target = findRedirect(location.pathname, pages());
    if (target) {
      setState({path: location.pathname, redirecting: true});
      history.replace(target + location.search + location.hash);
    } else {
      setState({path: location.pathname, redirecting: false});
    }
  }, [location.pathname, location.search, location.hash, history]);

  const suggestions = useMemo(
    () => (state && !state.redirecting ? suggestPages(state.path, pages()) : []),
    [state],
  );
  const ibmUrl = state && !state.redirecting ? ibmUrlFor(state.path) : null;
  const [query, setQuery] = useState('');
  useEffect(() => {
    if (state && !state.redirecting) setQuery(searchTermFromPath(state.path));
  }, [state]);

  const onSearch = (e: FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    history.push(q ? `/search?q=${encodeURIComponent(q)}` : '/search');
  };

  if (state?.redirecting) {
    return (
      <main className={clsx('container margin-vert--xl', className)} aria-busy="true">
        <p className={styles.redirecting}>
          <Translate id="notFound.redirecting" description="Shown for a moment on the 404 page while it opens the matching page">
            Opening the page…
          </Translate>
        </p>
      </main>
    );
  }

  return (
    <main className={clsx('container margin-vert--xl', className)}>
      <div className={styles.wrap}>
        <Heading as="h1" className={styles.title}>
          <Translate id="theme.NotFound.title" description="The title of the 404 page">
            Page Not Found
          </Translate>
        </Heading>
        <p>
          <Translate id="theme.NotFound.p1" description="The first paragraph of the 404 page">
            We could not find what you were looking for.
          </Translate>
          {state && state.path !== '/404.html' && (
            <>
              {' '}
              <code className={styles.path}>{state.path}</code>
            </>
          )}
        </p>
        {ibmUrl && (
          <p>
            <Translate
              id="notFound.ibm"
              description="404 page: the missing address looks like an IBM Quantum address; {link} is a link to that page on IBM's site"
              values={{
                link: (
                  <a href={ibmUrl} target="_blank" rel="noopener noreferrer">
                    <Translate id="notFound.ibm.link" description="Link text: open the same address on IBM Quantum's website">
                      open it on IBM Quantum
                    </Translate>
                  </a>
                ),
              }}>
              {'This address looks like an IBM Quantum page that is not mirrored here: {link}.'}
            </Translate>
          </p>
        )}

        <form className={styles.search} role="search" action="/search" method="get" onSubmit={onSearch}>
          <label htmlFor="notfound-search" className={styles.label}>
            <Translate id="notFound.search.label" description="Label of the search box on the 404 page">
              Search the site
            </Translate>
          </label>
          <div className={styles.searchRow}>
            <input
              id="notfound-search"
              type="search"
              name="q"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={translate({
                id: 'notFound.search.placeholder',
                message: 'e.g. transpile, VQE, Grover',
                description: 'Placeholder (example queries) in the search box on the 404 page',
              })}
              autoComplete="off"
              className={styles.input}
            />
            <button type="submit" className="button button--primary">
              <Translate id="notFound.search.button" description="Search button on the 404 page">
                Search
              </Translate>
            </button>
          </div>
        </form>

        {suggestions.length > 0 && (
          <section className={styles.section}>
            <Heading as="h2" className={styles.h2}>
              <Translate id="notFound.suggestions" description="Heading above a list of existing pages similar to the missing URL">
                Pages with a similar address
              </Translate>
            </Heading>
            <ul className={styles.suggestions}>
              {suggestions.map((p) => (
                <li key={p}>
                  <Link to={p}>{p}</Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className={styles.section}>
          <Heading as="h2" className={styles.h2}>
            <Translate id="notFound.browse" description="Heading above links to the main sections on the 404 page">
              Or start from here
            </Translate>
          </Heading>
          <ul className={styles.links}>
            <li>
              <Link to="/">
                <Translate id="notFound.link.home" description="404 page link to the home page">Home</Translate>
              </Link>
            </li>
            <li>
              <Link to="/tutorials">
                <Translate id="notFound.link.tutorials" description="404 page link to the tutorials overview">Tutorials</Translate>
              </Link>
            </li>
            <li>
              <Link to="/guides">
                <Translate id="notFound.link.guides" description="404 page link to the guides overview">Guides</Translate>
              </Link>
            </li>
            <li>
              <Link to="/learning">
                <Translate id="notFound.link.courses" description="404 page link to the list of courses and modules">Courses</Translate>
              </Link>
            </li>
          </ul>
        </section>
      </div>
    </main>
  );
}
