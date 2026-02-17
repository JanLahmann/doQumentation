import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

const config: Config = {
  title: 'doQumentation',
  tagline: 'Interactive IBM Quantum tutorials and courses',
  favicon: 'img/logo.svg',

  url: process.env.DQ_LOCALE_URL || 'https://doqumentation.org',
  baseUrl: '/',

  // GitHub pages deployment config
  organizationName: 'JanLahmann',
  projectName: 'doQumentation',
  trailingSlash: false,

  onBrokenLinks: 'warn',

  headTags: [
    // Preconnect hints for external resources
    {
      tagName: 'link',
      attributes: { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
    },
    {
      tagName: 'link',
      attributes: {
        rel: 'preconnect',
        href: 'https://fonts.gstatic.com',
        crossorigin: 'anonymous',
      },
    },
    {
      tagName: 'link',
      attributes: { rel: 'preconnect', href: 'https://cdn.jsdelivr.net' },
    },
    // Robots meta — max-snippet:-1 recommended for AI search
    {
      tagName: 'meta',
      attributes: {
        name: 'robots',
        content: 'index, follow, max-snippet:-1, max-image-preview:large',
      },
    },
    // Organization schema
    {
      tagName: 'script',
      attributes: { type: 'application/ld+json' },
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'Organization',
        name: 'doQumentation',
        url: 'https://doqumentation.org',
        logo: 'https://doqumentation.org/img/logo.svg',
        description:
          'Open-source frontend for IBM Quantum tutorials, courses, and documentation with live code execution.',
        sameAs: ['https://github.com/JanLahmann/doQumentation'],
      }),
    },
    // WebPage schema
    {
      tagName: 'script',
      attributes: { type: 'application/ld+json' },
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: 'doQumentation',
        description:
          'doQumentation adds a feature-rich, user-friendly, open-source frontend to IBM Quantum tutorials, courses, and documentation.',
        url: 'https://doqumentation.org',
        isPartOf: {
          '@type': 'WebSite',
          name: 'doQumentation',
          url: 'https://doqumentation.org',
        },
      }),
    },
    // SoftwareApplication schema
    {
      tagName: 'script',
      attributes: { type: 'application/ld+json' },
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'SoftwareApplication',
        name: 'doQumentation',
        applicationCategory: 'EducationalApplication',
        operatingSystem: 'Web, Docker, Raspberry Pi',
        description:
          'Open-source frontend for IBM Quantum documentation with live Jupyter code execution, simulator mode, and offline support.',
        url: 'https://doqumentation.org',
        offers: {
          '@type': 'Offer',
          price: '0',
          priceCurrency: 'USD',
        },
        license: 'https://www.apache.org/licenses/LICENSE-2.0',
      }),
    },
  ],

  i18n: {
    defaultLocale: 'en',
    locales: ['en', 'de', 'es', 'uk', 'fr', 'it', 'pt', 'ja', 'tl', 'ar', 'he'],
    localeConfigs: {
      en: { label: 'English', url: 'https://doqumentation.org' },
      de: { label: 'Deutsch', url: 'https://de.doqumentation.org' },
      es: { label: 'Español', url: 'https://es.doqumentation.org' },
      uk: { label: 'Українська', url: 'https://uk.doqumentation.org' },
      fr: { label: 'Français', url: 'https://fr.doqumentation.org' },
      it: { label: 'Italiano', url: 'https://it.doqumentation.org' },
      pt: { label: 'Português', url: 'https://pt.doqumentation.org' },
      ja: { label: '日本語', url: 'https://ja.doqumentation.org' },
      tl: { label: 'Filipino', url: 'https://tl.doqumentation.org' },
      ar: { label: 'العربية', direction: 'rtl', url: 'https://ar.doqumentation.org' },
      he: { label: 'עברית', direction: 'rtl', url: 'https://he.doqumentation.org' },
    },
  },

  // Enable Thebe for Jupyter execution (thebelab 0.4.x - battle-tested Binder integration)
  scripts: [
    {
      src: 'https://unpkg.com/thebelab@0.4.0/lib/index.js',
      async: true,
    },
  ],

  // KaTeX CSS for math rendering
  stylesheets: [
    {
      href: 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css',
      type: 'text/css',
      integrity: 'sha384-n8MVd4RsNIU0tAv4ct0nTaAbDJwPJzDEaqSD1odI+WdtXRGWt2kTvGFasHpSy3SV',
      crossorigin: 'anonymous',
    },
  ],

  clientModules: [
    require.resolve('./src/clientModules/pageTracker.ts'),
    require.resolve('./src/clientModules/displayPrefs.ts'),
    require.resolve('./src/clientModules/onboarding.ts'),
  ],

  themes: [
    [
      '@easyops-cn/docusaurus-search-local',
      {
        hashed: true,
        indexBlog: false,
        docsRouteBasePath: '/',
        language: ['en', 'de', 'es', 'fr', 'it', 'pt', 'ja', 'ar', 'he'],
      },
    ],
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          routeBasePath: '/', // Serve docs at root
          remarkPlugins: [remarkMath],
          rehypePlugins: [rehypeKatex],
          editUrl: 'https://github.com/JanLahmann/doQumentation/tree/main/',
        },
        blog: false, // Disable blog
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // Social card image
    image: 'img/rasqberry-social-card.png',

    // Global meta tags for social sharing and SEO
    metadata: [
      { property: 'og:type', content: 'website' },
      { property: 'og:site_name', content: 'doQumentation' },
      { name: 'twitter:title', content: 'doQumentation' },
      {
        name: 'twitter:description',
        content:
          'Open-source frontend for IBM Quantum tutorials, courses, and documentation with live code execution.',
      },
      { name: 'theme-color', content: '#161616' },
    ],

    navbar: {
      title: 'doQumentation',
      logo: {
        alt: 'doQumentation Logo',
        src: 'img/logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'tutorialsSidebar',
          position: 'left',
          label: 'Tutorials',
        },
        {
          to: '/guides',
          label: 'Guides',
          position: 'left',
        },
        {
          to: '/learning/courses/basics-of-quantum-information',
          label: 'Courses',
          position: 'left',
        },
        {
          to: '/learning/modules/computer-science',
          label: 'Modules',
          position: 'left',
        },
        {
          href: 'https://quantum.cloud.ibm.com/docs/en/api',
          label: 'API Reference',
          position: 'left',
        },
        {
          type: 'localeDropdown',
          position: 'right',
          className: 'navbar-locale-dropdown',
        },
        {
          href: '/jupyter-settings',
          label: 'Settings',
          position: 'right',
          className: 'header-settings-link',
          'aria-label': 'Settings',
        },
        // Dark mode toggle is auto-placed here by Docusaurus (CSS order: 3)
        {
          href: 'https://github.com/JanLahmann/doQumentation',
          label: 'GitHub',
          position: 'right',
          className: 'header-github-link',
          'aria-label': 'GitHub repository',
        },
      ],
    },
    
    footer: {
      style: 'dark',
      links: [
        {
          title: 'doQumentation',
          items: [
            {
              label: 'Features',
              to: '/features',
            },
            {
              label: 'Settings',
              to: '/jupyter-settings',
            },
            {
              label: 'GitHub',
              href: 'https://github.com/JanLahmann/doQumentation',
            },
          ],
        },
        {
          title: 'RasQberry',
          items: [
            {
              label: 'RasQberry',
              href: 'https://rasqberry.org',
            },
            {
              label: 'RasQberry GitHub',
              href: 'https://github.com/JanLahmann/RasQberry-Two',
            },
          ],
        },
        {
          title: 'IBM Quantum & Qiskit',
          items: [
            {
              label: 'IBM Quantum',
              href: 'https://quantum.cloud.ibm.com',
            },
            {
              label: 'Qiskit Documentation',
              href: 'https://quantum.cloud.ibm.com/docs/en/guides',
            },
            {
              label: 'Qiskit Docs GitHub',
              href: 'https://github.com/Qiskit/documentation',
            },
            {
              label: 'Qiskit Slack',
              href: 'https://qisk.it/join-slack',
            },
          ],
        },
      ],
      copyright: `<a href="https://github.com/Qiskit/documentation">Qiskit documentation</a> content © IBM Corp. Code is licensed under Apache 2.0; content (tutorials, courses, media) under CC BY-SA 4.0.<br/>IBM, IBM Quantum, and Qiskit are trademarks of IBM Corporation.<br/>doQumentation is part of the <a href="https://rasqberry.org/">RasQberry</a> project and is not affiliated with, endorsed by, or sponsored by IBM Corporation.`,
    },
    
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['python', 'bash', 'json', 'shell-session', 'yaml', 'toml', 'diff', 'markup'],
    },

    // Custom config for Jupyter integration
    // This is read by our ExecutableCode component
    customFields: {
      jupyter: {
        // Default Jupyter server URL (overridden at runtime)
        defaultUrl: 'http://localhost:8888',
        defaultToken: 'rasqberry',
        // Binder URL for GitHub Pages fallback
        binderUrl: 'https://mybinder.org/v2/gh/JanLahmann/Qiskit-documentation/main',
      },
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
