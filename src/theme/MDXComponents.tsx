import React from 'react';
import MDXComponents from '@theme-original/MDXComponents';
import Admonition from '@theme/Admonition';
import DefinitionTooltip from '@site/src/components/CourseComponents/DefinitionTooltip';
import Figure from '@site/src/components/CourseComponents/Figure';
import IBMVideo from '@site/src/components/CourseComponents/IBMVideo';
import LaunchExamButton from '@site/src/components/CourseComponents/LaunchExamButton';
import OpenInLabBanner from '@site/src/components/OpenInLabBanner';
import ResumeCard from '@site/src/components/ResumeCard';
import RecentPages from '@site/src/components/RecentPages';
import BookmarksList from '@site/src/components/BookmarksList';
import Card from '@site/src/components/GuideComponents/Card';
import CardGroup from '@site/src/components/GuideComponents/CardGroup';
import OperatingSystemTabs from '@site/src/components/GuideComponents/OperatingSystemTabs';
import CodeAssistantAdmonition from '@site/src/components/GuideComponents/CodeAssistantAdmonition';

// Fallback for any <Image> JSX not converted to markdown during sync
function Image(props: React.ImgHTMLAttributes<HTMLImageElement>) {
  return <img {...props} />;
}

// Stubs for IBM Accordion/AccordionItem — used in some course notebooks for Q&A.
// Render as native <details>/<summary> for graceful fallback.
function Accordion({ children }: { children?: React.ReactNode }) {
  return <div className="dq-accordion">{children}</div>;
}
function AccordionItem({ title, children }: { title?: string; children?: React.ReactNode }) {
  return (
    <details className="dq-accordion-item" style={{ margin: '0.5rem 0', padding: '0.5rem 1rem', border: '1px solid var(--ifm-color-emphasis-300)', borderRadius: '4px' }}>
      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>{title || 'Details'}</summary>
      <div style={{ marginTop: '0.5rem' }}>{children}</div>
    </details>
  );
}

export default {
  ...MDXComponents,
  Admonition,
  DefinitionTooltip,
  Figure,
  Image,
  IBMVideo,
  LaunchExamButton,
  OpenInLabBanner,
  Card,
  CardGroup,
  OperatingSystemTabs,
  CodeAssistantAdmonition,
  ResumeCard,
  RecentPages,
  BookmarksList,
  Accordion,
  AccordionItem,
};
