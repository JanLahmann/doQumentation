import React from 'react';
import MDXComponents from '@theme-original/MDXComponents';
import Admonition from '@theme/Admonition';
import DefinitionTooltip from '@site/src/components/CourseComponents/DefinitionTooltip';
import Figure from '@site/src/components/CourseComponents/Figure';
import IBMVideo from '@site/src/components/CourseComponents/IBMVideo';
import LaunchExamButton from '@site/src/components/CourseComponents/LaunchExamButton';
import OpenInLabBanner from '@site/src/components/OpenInLabBanner';
import ResumeCard from '@site/src/components/ResumeCard';
import Card from '@site/src/components/GuideComponents/Card';
import CardGroup from '@site/src/components/GuideComponents/CardGroup';
import OperatingSystemTabs from '@site/src/components/GuideComponents/OperatingSystemTabs';
import CodeAssistantAdmonition from '@site/src/components/GuideComponents/CodeAssistantAdmonition';

// Fallback for any <Image> JSX not converted to markdown during sync
function Image(props: React.ImgHTMLAttributes<HTMLImageElement>) {
  return <img {...props} />;
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
};
