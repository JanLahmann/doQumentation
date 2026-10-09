/**
 * Course catalogue at /learning/courses. The route and its data come from
 * plugins/course-catalogue (src/data/courses.json + the localized sidebar and
 * course overview pages), so course titles and descriptions are translated
 * on every locale build. Progress uses the same visited-pages store as the
 * sidebar's "6/18" counters (read-only).
 */
import React, {useEffect, useState} from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
import Translate, {translate} from '@docusaurus/Translate';
import {getVisitedPages} from '../../config/preferences';
import {PAGE_VISITED_EVENT} from '../../clientModules/pageTracker';
import styles from './styles.module.css';

type Entry = {
  slug: string;
  title: string;
  description: string;
  href: string;
  pages: string[];
};
type Course = Entry & {
  group: string;
  hours: number | null;
  level: string | null;
  isNew: boolean;
  series: number | null;
};
type Catalogue = {
  groups: string[];
  beginnerChoices: {kind: string; slug: string}[];
  courses: Course[];
  modules: Entry[];
};

// Static ids, so `write-translations` finds every string.
function groupText(id: string): {title: string; text: string} {
  switch (id) {
    case 'get-started':
      return {
        title: translate({id: 'catalogue.group.getStarted.title', message: 'Get started', description: 'Course catalogue group heading'}),
        text: translate({id: 'catalogue.group.getStarted.text', message: 'Run real quantum programs from the first lesson.', description: 'Course catalogue: one line under the "Get started" heading'}),
      };
    case 'foundations':
      return {
        title: translate({id: 'catalogue.group.foundations.title', message: 'Foundations', description: 'Course catalogue group heading'}),
        text: translate({id: 'catalogue.group.foundations.text', message: 'A four-course series on quantum information and computation by John Watrous. Take them in order.', description: 'Course catalogue: one line under the "Foundations" heading'}),
      };
    case 'techniques':
      return {
        title: translate({id: 'catalogue.group.techniques.title', message: 'Techniques & applications', description: 'Course catalogue group heading'}),
        text: translate({id: 'catalogue.group.techniques.text', message: 'Algorithms, error mitigation and applications for today\'s quantum computers.', description: 'Course catalogue: one line under the "Techniques & applications" heading'}),
      };
    case 'business':
      return {
        title: translate({id: 'catalogue.group.business.title', message: 'Business', description: 'Course catalogue group heading'}),
        text: translate({id: 'catalogue.group.business.text', message: 'Quantum computing for decision-makers and project leads. No technical background needed.', description: 'Course catalogue: one line under the "Business" heading'}),
      };
    default:
      return {title: id, text: ''};
  }
}

function levelText(level: string): string {
  switch (level) {
    case 'beginner':
      return translate({id: 'catalogue.level.beginner', message: 'Beginner', description: 'Course level'});
    case 'intermediate':
      return translate({id: 'catalogue.level.intermediate', message: 'Intermediate', description: 'Course level'});
    case 'advanced':
      return translate({id: 'catalogue.level.advanced', message: 'Advanced', description: 'Course level'});
    default:
      return level;
  }
}

function hoursText(hours: number): string {
  return translate(
    {id: 'catalogue.hours', message: '≈{hours} h', description: 'Estimated course length in hours, e.g. "≈5 h"'},
    {hours: String(hours)},
  );
}

function stripSlash(p: string): string {
  return p.replace(/\/+$/, '') || '/';
}

/** Visited-page set, refreshed when the page tracker records a visit. */
function useVisited(): Set<string> | null {
  const [visited, setVisited] = useState<Set<string> | null>(null);
  useEffect(() => {
    const refresh = () => setVisited(getVisitedPages());
    refresh();
    window.addEventListener(PAGE_VISITED_EVENT, refresh);
    return () => window.removeEventListener(PAGE_VISITED_EVENT, refresh);
  }, []);
  return visited;
}

function Progress({entry, visited}: {entry: Entry; visited: Set<string> | null}) {
  if (!visited || entry.pages.length === 0) return null;
  const total = entry.pages.length;
  const done = entry.pages.filter((p) => visited.has(stripSlash(p))).length;
  if (done === 0) return null;
  const label = translate(
    {id: 'catalogue.progress', message: '{visited} of {total} pages visited', description: 'Course catalogue card: learner progress'},
    {visited: String(done), total: String(total)},
  );
  return (
    <div className={styles.progress} data-testid="course-progress">
      <div className={styles.progressBar} aria-hidden="true">
        <div className={styles.progressFill} style={{width: `${Math.round((done / total) * 100)}%`}} />
      </div>
      <span className={styles.progressText}>{label}</span>
    </div>
  );
}

function CourseCard({course, visited}: {course: Course; visited: Set<string> | null}) {
  return (
    <Link to={course.href} className={styles.card} data-course={course.slug}>
      {course.series !== null && (
        <span className={styles.series}>
          {translate(
            {id: 'catalogue.seriesNumber', message: 'Course {n}', description: 'Position of a course in the Foundations series, e.g. "Course 1"'},
            {n: String(course.series)},
          )}
        </span>
      )}
      <span className={styles.cardTitle}>{course.title}</span>
      {course.description && <span className={styles.cardDesc}>{course.description}</span>}
      <span className={styles.meta}>
        {course.level && <span className={styles.chip}>{levelText(course.level)}</span>}
        {course.hours !== null && <span className={styles.chip}>{hoursText(course.hours)}</span>}
        {course.isNew && (
          <span className={`${styles.chip} ${styles.chipNew}`}>
            {translate({id: 'catalogue.new', message: 'New', description: 'Badge on a recently added course'})}
          </span>
        )}
      </span>
      <Progress entry={course} visited={visited} />
    </Link>
  );
}

export default function CourseCatalogue({catalogue}: {catalogue: Catalogue}): React.JSX.Element {
  const visited = useVisited();
  const bySlug = new Map(catalogue.courses.map((c) => [c.slug, c]));
  const choices = catalogue.beginnerChoices
    .map((b) => ({kind: b.kind, course: bySlug.get(b.slug)}))
    .filter((b): b is {kind: string; course: Course} => !!b.course);

  return (
    <Layout
      title={translate({id: 'catalogue.title', message: 'Courses', description: 'Course catalogue page title'})}
      description={translate({id: 'catalogue.description', message: 'All quantum computing courses from IBM Quantum Learning, grouped from first steps to advanced topics, with time estimates and your progress.', description: 'Course catalogue meta description'})}>
      <main className={`container margin-vert--lg ${styles.page}`}>
        <h1>
          <Translate id="catalogue.heading" description="Course catalogue H1">Courses</Translate>
        </h1>
        <p className={styles.lead}>
          <Translate id="catalogue.lead" description="Course catalogue intro paragraph">
            Every course from IBM Quantum Learning, with runnable code on each page. Grouping and time estimates follow IBM's catalogue.
          </Translate>
        </p>

        {choices.length > 0 && (
          <section className={styles.start} aria-labelledby="catalogue-start">
            <h2 id="catalogue-start" className={styles.startHeading}>
              <Translate id="catalogue.start.heading" description="Course catalogue: heading of the two beginner choices">New to quantum computing? Start with one of these</Translate>
            </h2>
            <div className={styles.startGrid}>
              {choices.map(({kind, course}) => (
                <Link key={course.slug} to={course.href} className={styles.startCard} data-start={kind}>
                  <span className={styles.startKind}>
                    {kind === 'hands-on'
                      ? translate({id: 'catalogue.start.handsOn', message: 'Hands-on first', description: 'Beginner choice: learn by running code first'})
                      : translate({id: 'catalogue.start.theory', message: 'Theory first', description: 'Beginner choice: learn the maths first'})}
                  </span>
                  <span className={styles.cardTitle}>
                    {course.title}
                    {course.hours !== null && <> ({hoursText(course.hours)})</>}
                  </span>
                  <span className={styles.cardDesc}>
                    {kind === 'hands-on'
                      ? translate({id: 'catalogue.start.handsOn.text', message: 'Run circuits on real quantum hardware from the first lesson. No physics degree needed.', description: 'Beginner choice: why to pick the hands-on course'})
                      : translate({id: 'catalogue.start.theory.text', message: 'Build the maths step by step: states, measurements, circuits, entanglement. Assumes basic linear algebra.', description: 'Beginner choice: why to pick the theory course'})}
                  </span>
                  <Progress entry={course} visited={visited} />
                </Link>
              ))}
            </div>
          </section>
        )}

        {catalogue.groups.map((group) => {
          const courses = catalogue.courses.filter((c) => c.group === group);
          if (courses.length === 0) return null;
          const {title, text} = groupText(group);
          return (
            <section key={group} className={styles.group} aria-labelledby={`catalogue-${group}`}>
              <h2 id={`catalogue-${group}`}>{title}</h2>
              {text && <p className={styles.groupText}>{text}</p>}
              <div className={styles.grid}>
                {courses.map((c) => (
                  <CourseCard key={c.slug} course={c} visited={visited} />
                ))}
              </div>
            </section>
          );
        })}

        {catalogue.modules.length > 0 && (
          <section className={styles.group} aria-labelledby="catalogue-modules">
            <h2 id="catalogue-modules">
              <Translate id="catalogue.modules.heading" description="Course catalogue: heading of the modules section">Modules for the classroom</Translate>
            </h2>
            <p className={styles.groupText}>
              <Translate id="catalogue.modules.text" description="Course catalogue: one line under the modules heading">
                Short, self-contained lessons with Qiskit code and practice questions, made for school and university classes.
              </Translate>
            </p>
            <div className={styles.grid}>
              {catalogue.modules.map((m) => (
                <Link key={m.slug} to={m.href} className={styles.card} data-module={m.slug}>
                  <span className={styles.cardTitle}>{m.title}</span>
                  {m.description && <span className={styles.cardDesc}>{m.description}</span>}
                  <Progress entry={m} visited={visited} />
                </Link>
              ))}
            </div>
          </section>
        )}
      </main>
    </Layout>
  );
}
