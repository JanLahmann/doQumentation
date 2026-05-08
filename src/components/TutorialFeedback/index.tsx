/**
 * TutorialFeedback — DEPRECATED render-as-null wrapper.
 *
 * The feedback widget moved into the unified DocItem footer (see
 * src/theme/DocItem/Footer/index.tsx, which renders FeedbackWidget for
 * tutorial pages). This file stays as a no-op so the ~240 MDX files
 * that still import and render <TutorialFeedback /> inline don't need
 * to be rewritten — they just produce nothing now.
 *
 * New tutorials should NOT add <TutorialFeedback /> anymore; the footer
 * adds it automatically based on the doc's source path. Existing
 * inline calls can be removed in a future cleanup pass.
 */

export default function TutorialFeedback(): null {
  return null;
}
