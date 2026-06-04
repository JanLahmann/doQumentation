import React from 'react';
import Tabs from '@theme/Tabs';

interface OperatingSystemTabsProps {
  children: React.ReactNode;
}

/**
 * Stub for IBM's OperatingSystemTabs component.
 * Maps to Docusaurus Tabs with OS grouping.
 *
 * Children are authored as <TabItem> elements in MDX; Docusaurus' Tabs types its
 * children narrowly (TabItem | TabItem[]) while our prop is the broader ReactNode,
 * so this pass-through stub casts to satisfy the Tabs signature.
 */
export default function OperatingSystemTabs({ children }: OperatingSystemTabsProps) {
  return (
    <Tabs groupId="os">
      {children as React.ComponentProps<typeof Tabs>['children']}
    </Tabs>
  );
}
