import React from 'react';

interface IBMVideoProps {
  id: string;
  title?: string;
}

/**
 * IBM Video ID → YouTube video ID mapping.
 * Sources: upstream content (explicit YouTube links) + Qiskit YouTube channel search.
 */
const YOUTUBE_MAP: Record<string, string> = {
  // Basics of Quantum Information — John Watrous
  '134056207': '3-c4xJa7Flk',
  '134627974': 'DfZZS8Spe7U',
  '134056224': '30U2DTfIrOU',
  '134056223': 'GSsElSQgMbU',
  // Fundamentals of Quantum Algorithms — John Watrous
  '134056222': '2wxxvwRGANQ',
  '134056235': '2wticzHE1vs',
  '134056243': 'hnpjC8WQVrQ',
  '134056217': '4nT0BTUxhJY',
  // General Formulation of Quantum Information — John Watrous
  '134056231': 'CeK9ry8G8HQ',
  '134063422': 'cMl-xIDSmXI',
  '134063423': 'Xi9YTYzQErY',
  '134063424': 'jemWEdnJTnI',
  // Foundations of Quantum Error Correction — John Watrous
  '134082557': 'OoQSdcKAIZc',
  '134212334': '3ib2JP_LeIU',
  '134313287': '9TCIOm8gcVQ',
  '134352398': 'aeaqXh2XXMk',
  // Quantum Computing in Practice — Olivia Lanes
  '134063425': 'sVRpKhCfKRI',
  '134063416': 'NTplT4WnNbk',
  '134063426': '33QmsXhIlpU',
  '134397390': 'BiKpHaev0XI',
  '134460549': '7cbNnxDHqeQ',
  '134063421': 'P3s7TIMIvZ0',
  // Quantum Mechanics modules — Katie McCormick
  '134413660': 'pcGIBacW-q0',
  '134413671': 'TZ-sUHK8vVQ',
  '134413665': 'pS69lqCMdy8',
  '134413662': '3h3pwrECbb8',
  // Computer Science modules — Katie McCormick
  '134413658': 'R0SOqLwLOR0',
  '134413680': 'jxqnzltpDdE',
  '134413695': 'QcK0GK7DUh8',
  // Quantum Diagonalization Algorithms — Chris Porter (found on Qiskit YouTube)
  '134325501': 'u53IyCR7sUM',
  '134325510': 'EAW8-LKalCE',
  '134325519': 'DUq-0r-Prw0',
};

/**
 * Renders an embedded video player for IBM Quantum course content.
 *
 * Strategy:
 * 1. If a YouTube equivalent exists → embed YouTube (better UX, no restrictions)
 * 2. Otherwise → embed via video.ibm.com/embed/recorded/{id} (unlisted but working)
 */
export default function IBMVideo({ id, title }: IBMVideoProps) {
  const youtubeId = YOUTUBE_MAP[id];

  const iframeSrc = youtubeId
    ? `https://www.youtube-nocookie.com/embed/${youtubeId}`
    : `https://video.ibm.com/embed/recorded/${id}`;

  return (
    <div style={{ margin: '1rem 0' }}>
      <div
        style={{
          position: 'relative',
          paddingBottom: '56.25%',
          height: 0,
          overflow: 'hidden',
          borderRadius: '8px',
        }}
      >
        <iframe
          src={iframeSrc}
          title={title || 'Video'}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            border: 0,
          }}
          allowFullScreen
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          loading="lazy"
        />
      </div>
    </div>
  );
}
