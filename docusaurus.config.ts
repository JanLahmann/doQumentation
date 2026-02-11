import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

const config: Config = {
  title: 'doQumentation',
  tagline: 'Interactive IBM Quantum tutorials and courses',
  favicon: 'img/favicon.ico',

  url: 'https://doqumentation.org',
  baseUrl: '/',

  // GitHub pages deployment config
  organizationName: 'JanLahmann',
  projectName: 'doQumentation',
  trailingSlash: false,

  onBrokenLinks: 'warn',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
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
          href: '/jupyter-settings',
          label: '⚙ Settings',
          position: 'right',
        },
        {
          href: 'https://github.com/JanLahmann/doQumentation',
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
          title: 'RasQberry',
          items: [
            {
              label: 'Features',
              to: '/features',
            },
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
