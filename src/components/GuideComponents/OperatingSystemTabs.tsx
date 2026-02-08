import React from 'react';
import Tabs from '@theme/Tabs';

interface OperatingSystemTabsProps {
  children: React.ReactNode;
}

/**
 * Stub for IBM's OperatingSystemTabs component.
 * Maps to Docusaurus Tabs with OS grouping.
 */
export default function OperatingSystemTabs({ children }: OperatingSystemTabsProps) {
  return (
    <Tabs groupId="os">
      {children}
    </Tabs>
  );
}
