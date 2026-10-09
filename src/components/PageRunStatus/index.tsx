import Link from '@docusaurus/Link';
import {translate} from '@docusaurus/Translate';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import status from '../../config/pageRunStatus.json';
import './styles.css';

type Category = 'runs' | 'needs-ibm' | 'heavy' | 'issue';

const pages = status.pages as Record<string, Category>;
const details = status.details as Record<string, string>;

const ICONS: Record<Category, string> = {
  runs: '✓',        // ✓
  'needs-ibm': '☁', // ☁
  heavy: '⏱',       // ⏱
  issue: '⚠',       // ⚠
};

function label(category: Category): string {
  switch (category) {
    case 'runs':
      return translate({id: 'runStatus.runs', message: 'Runs in Simulator Mode'});
    case 'needs-ibm':
      return translate({id: 'runStatus.needsIbm', message: 'Parts need an IBM Quantum account'});
    case 'heavy':
      return translate({id: 'runStatus.heavy', message: 'Very slow or too large for Simulator Mode'});
    case 'issue':
      return translate({id: 'runStatus.issue', message: 'Some code failed in our last test'});
  }
}

function explanation(category: Category, date: string): string {
  switch (category) {
    case 'runs':
      return translate(
        {id: 'runStatus.runs.explain', message: 'In our automated test on {date}, every code cell on this page ran in Simulator Mode, without an IBM Quantum account.'},
        {date});
    case 'needs-ibm':
      return translate(
        {id: 'runStatus.needsIbm.explain', message: 'In our automated test on {date}, a cell on this page needed IBM Quantum (for example Qiskit Functions, Qiskit Serverless or the results of a job that ran on real hardware). The cells before it run in Simulator Mode; to run the rest, add your IBM Quantum credentials in Settings.'},
        {date});
    case 'heavy':
      return translate(
        {id: 'runStatus.heavy.explain', message: 'In our automated test on {date}, a cell on this page ran for more than 5 minutes or ran out of memory. Here it may take very long or stop; JupyterLab or your own computer is a better fit for this page.'},
        {date});
    case 'issue':
      return translate(
        {id: 'runStatus.issue.explain', message: 'In our automated test on {date}, a cell on this page failed in Simulator Mode: a package missing from this environment, a Qiskit API newer than the one installed here, or a bug in the notebook. The cells before it run. If it still fails for you, please report it.'},
        {date});
  }
}

function reportUrl(notebookPath: string, detail: string): string {
  const params = new URLSearchParams({
    template: 'execution-error.yml',
    title: `Execution error on ${notebookPath.replace(/\.ipynb$/, '')}`,
    page: window.location.href,
    error: detail,
  });
  return `https://github.com/JanLahmann/doQumentation/issues/new?${params}`;
}

/**
 * One-line label in the "Open in" banner saying whether this page's code ran
 * in Simulator Mode in the last notebook sweep (src/config/pageRunStatus.json,
 * written by scripts/notebook-sweep/make_page_status.py). Pages the sweep did
 * not cover, or whose code changed since, render nothing. Must render inside
 * BrowserOnly (reads window.location for the report link).
 */
export default function PageRunStatus({ notebookPath }: { notebookPath: string }) {
  const { i18n: { currentLocale } } = useDocusaurusContext();
  const category = pages[notebookPath];
  if (!category) return null;

  let date = status.sweepDate;
  try {
    date = new Date(`${status.sweepDate}T00:00:00Z`).toLocaleDateString(currentLocale, {
      year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC',
    });
  } catch { /* unknown locale: keep the ISO date */ }

  const detail = details[notebookPath];
  return (
    <details className={`dq-run-status dq-run-status--${category}`}>
      <summary>
        <span className="dq-run-status__icon" aria-hidden="true">{ICONS[category]}</span>
        {label(category)}
      </summary>
      <div className="dq-run-status__body">
        <p>{explanation(category, date)}</p>
        {detail && <p><code dir="ltr">{detail}</code></p>}
        <p className="dq-run-status__meta">
          {translate(
            {id: 'runStatus.meta', message: 'Tested with {image}. Results can change as the page or the environment is updated.'},
            {image: status.image})}
          {category === 'needs-ibm' && (
            <> <Link to="/jupyter-settings#ibm-quantum">{translate({id: 'runStatus.settings', message: 'Open Settings'})}</Link></>
          )}
          {category === 'issue' && (
            <> <a href={reportUrl(notebookPath, detail ?? '')} target="_blank" rel="noopener noreferrer">
              {translate({id: 'runStatus.report', message: 'Report a problem'})}
            </a></>
          )}
        </p>
      </div>
    </details>
  );
}
