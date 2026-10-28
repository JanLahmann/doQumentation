/**
 * Learning paths at /learning-paths: IBM Quantum Learning's paths
 * (src/data/learning-paths.json), each step linked to our page with the
 * learner's progress. The route and its data come from
 * plugins/course-catalogue, which resolves every step to its localized
 * title, link and pages. A landing page: indexed, in the sitemap.
 */
import React from 'react';
import Link from '@docusaurus/Link';
import Translate, {translate} from '@docusaurus/Translate';
import LandingPage from '@site/src/components/LandingPage';
import {landingLinks} from '@site/src/components/LandingPage/links';
import {levelText, hoursText, stripSlash, useVisited} from '@site/src/components/CourseCatalogue';
import styles from './styles.module.css';

type Step = {
  id: string;
  hours: number;
  kind: 'course' | 'module' | 'tutorial' | 'guide';
  title: string;
  href: string;
  pages: string[];
};
/** `ibm`: the path's slug on IBM Quantum Learning (its ?modal= value). */
type Level = {level: string | null; hours: number; ibm: string; steps: Step[]};
type Path = {id: string; levels: Level[]};
type Data = {source: string; paths: Path[]};

const IBM_LEARNING = 'https://quantum.cloud.ibm.com/learning/en';

// Static ids, so `write-translations` finds every string.
function pathText(id: string): {name: string; text: string} {
  switch (id) {
    case 'introduction':
      return {
        name: translate({id: 'paths.introduction.name', message: 'Introduction to quantum'}),
        text: translate({id: 'paths.introduction.text', message: 'Key terms, your first circuits and where quantum computing is used today.'}),
      };
    case 'optimization':
      return {
        name: translate({id: 'paths.optimization.name', message: 'Optimization'}),
        text: translate({id: 'paths.optimization.text', message: 'QAOA for problems like Max-Cut and methods for lowest eigenvalues, then applications such as the market split problem.'}),
      };
    case 'data-science':
      return {
        name: translate({id: 'paths.dataScience.name', message: 'Data science'}),
        text: translate({id: 'paths.dataScience.text', message: 'Quantum search, kernels and machine learning, then the quantum Fourier transform and Shor\'s algorithm.'}),
      };
    case 'physics-chemistry':
      return {
        name: translate({id: 'paths.physicsChemistry.name', message: 'Physics and chemistry'}),
        text: translate({id: 'paths.physicsChemistry.text', message: 'VQE for molecules and spin chains, then sample-based and Krylov diagonalization at utility scale.'}),
      };
    case 'algorithms':
      return {
        name: translate({id: 'paths.algorithms.name', message: 'Quantum algorithm development'}),
        text: translate({id: 'paths.algorithms.text', message: 'From the fundamentals of quantum algorithms to diagonalization, QAOA and error correction, in three levels.'}),
      };
    case 'qise':
      return {
        name: translate({id: 'paths.qise.name', message: 'Quantum information science and engineering (QISE)'}),
        text: translate({id: 'paths.qise.text', message: 'Algorithms, the general theory of quantum information and error correction.'}),
      };
    default:
      return {name: id, text: ''};
  }
}

function kindText(kind: Step['kind']): string {
  switch (kind) {
    case 'course':
      return translate({id: 'paths.kind.course', message: 'Course'});
    case 'module':
      return translate({id: 'paths.kind.module', message: 'Module'});
    case 'tutorial':
      return translate({id: 'paths.kind.tutorial', message: 'Tutorial'});
    default:
      return translate({id: 'paths.kind.guide', message: 'Guide'});
  }
}

/** Pages of a step the learner has visited, and whether the step is done. */
function stepProgress(step: Step, visited: Set<string> | null): {done: number; total: number; complete: boolean} {
  const total = step.pages.length;
  const done = visited ? step.pages.filter((p) => visited.has(stripSlash(p))).length : 0;
  return {done, total, complete: total > 0 && done === total};
}

function LevelCard({path, level, visited}: {path: Path; level: Level; visited: Set<string> | null}) {
  const progress = level.steps.map((s) => stepProgress(s, visited));
  const complete = progress.filter((p) => p.complete).length;
  return (
    <div className={styles.level} data-path={path.id} data-level={level.level ?? 'all'}>
      <div className={styles.levelHead}>
        {level.level && <span className={styles.chip}>{levelText(level.level)}</span>}
        <span className={styles.chip}>{hoursText(level.hours)}</span>
        {visited && complete > 0 && (
          <span className={styles.levelDone}>
            {translate(
              {id: 'paths.stepsDone', message: '{done} of {total} steps done'},
              {done: String(complete), total: String(level.steps.length)},
            )}
          </span>
        )}
      </div>
      <ol className={styles.steps}>
        {level.steps.map((s, i) => {
          const p = progress[i];
          return (
            <li key={s.id} className={p.complete ? styles.stepComplete : undefined}>
              <Link to={s.href}>{s.title}</Link>
              <span className={styles.stepMeta}>
                {kindText(s.kind)} · {hoursText(s.hours)}
                {p.complete ? ' · ✓' : p.done > 0 && p.total > 1 ? ` · ${p.done}/${p.total}` : ''}
              </span>
            </li>
          );
        })}
      </ol>
      <a className={styles.ibmLink} href={`${IBM_LEARNING}?modal=${level.ibm}`} target="_blank" rel="noopener noreferrer">
        {translate({id: 'paths.onIbm', message: 'This path on IBM Quantum Learning'})} ↗
      </a>
    </div>
  );
}

/** Why follow the paths here: one line per doQumentation feature, with its landing page. */
function Benefits() {
  const items = [
    {to: '/run-qiskit-in-browser', text: translate({id: 'paths.benefit.run', message: 'Run the code of every step right on the page, with nothing to install.'})},
    {to: '/simulator-mode', text: translate({id: 'paths.benefit.simulator', message: 'Start without an IBM Quantum account: the code runs on a simulator by default.'})},
    {to: '/learning-progress', text: translate({id: 'paths.benefit.progress', message: 'See your progress on every step, kept in your browser with no sign-up.'})},
    {to: '/open-in-colab', text: translate({id: 'paths.benefit.colab', message: 'Open any notebook in Google Colab or JupyterLab.'})},
    {to: '/workshop-setup', text: translate({id: 'paths.benefit.workshop', message: 'Teach a path in class, from the cloud or offline from a Raspberry Pi.'})},
  ];
  return (
    <ul>
      {items.map((i) => (
        <li key={i.to}><Link to={i.to}>{i.text}</Link></li>
      ))}
      <li>{translate({id: 'paths.benefit.languages', message: 'Read the paths in 17 languages besides English.'})}</li>
    </ul>
  );
}

export default function LearningPaths({data}: {data: Data}): React.JSX.Element {
  const visited = useVisited();
  return (
    <LandingPage
      title={translate({id: 'paths.title', message: 'IBM Quantum Learning Paths, Runnable in Your Browser'})}
      description={translate({id: 'paths.description', message: "IBM Quantum's learning paths for optimization, data science, chemistry, algorithms and more, with runnable code on every page and your progress. No account needed."})}
      heading={translate({id: 'paths.heading', message: 'IBM Quantum learning paths'})}
      intro={
        <>
          <p>
            <Translate
              id="paths.intro.ibm"
              values={{link: <a href={data.source} target="_blank" rel="noopener noreferrer">IBM Quantum Learning</a>}}>
              {"These learning paths are IBM's. IBM Quantum publishes them on {link}: each one an order in which to work through IBM's courses, tutorials and guides for one area, at one or more levels. The steps, their order and the time estimates below are IBM's; doQumentation only links each step to its page here."}
            </Translate>
          </p>
        </>
      }
      cta={{to: '/learning/courses', label: translate({id: 'paths.cta', message: 'Or browse all courses'})}}
      sections={[
        {heading: translate({id: 'paths.why.heading', message: 'Why follow them on doQumentation'}), body: <Benefits />},
        ...data.paths.map((p) => {
        const {name, text} = pathText(p.id);
        return {
          heading: name,
          body: (
            <>
              {text && <p>{text}</p>}
              <div className={styles.levels}>
                {p.levels.map((l) => (
                  <LevelCard key={l.level ?? 'all'} path={p} level={l} visited={visited} />
                ))}
              </div>
            </>
          ),
        };
      })]}
      faq={[
        {question: translate({id: 'paths.faq.whose.q', message: 'Are these learning paths from doQumentation?'}),
          answer: translate({id: 'paths.faq.whose.a', message: 'No. They are IBM Quantum\'s, published on IBM Quantum Learning, and doQumentation shows them as IBM publishes them. What doQumentation adds is the way you work through them: runnable code, a simulator without an account, progress tracking and translations.'})},
        {question: translate({id: 'paths.faq.what.q', message: 'What is a learning path?'}),
          answer: translate({id: 'paths.faq.what.a', message: 'An ordered list of courses, tutorials and guides for one area, such as optimization or chemistry, with an estimate of the time each step takes. IBM Quantum Learning publishes them; doQumentation links every step to its runnable page.'})},
        {question: translate({id: 'paths.faq.progress.q', message: 'How is my progress counted?'}),
          answer: translate({id: 'paths.faq.progress.a', message: 'A step is done when you have read all of its pages: one page for a tutorial or guide, every lesson for a course. Progress is kept in your browser, with no account.'})},
        {question: translate({id: 'paths.faq.badge.q', message: 'Do I get IBM\'s badge?'}),
          answer: translate({id: 'paths.faq.badge.a', message: 'No. IBM\'s badges are earned on IBM Quantum Learning with an IBM Quantum account. doQumentation is an independent mirror of the open-source content.'})},
        {question: translate({id: 'paths.faq.order.q', message: 'Do I have to follow the order?'}),
          answer: translate({id: 'paths.faq.order.a', message: 'No, but the order is a good one: each step builds on the ones before it. Within a path, the beginner level comes first.'})},
      ]}
      related={landingLinks('paths')}
    />
  );
}
