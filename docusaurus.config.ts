import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

const config: Config = {
  title: 'RasQberry Tutorials',
  tagline: 'IBM Quantum tutorials with local Jupyter execution',
  favicon: 'img/favicon.ico',

  // Set the production url of your site here
  // For GitHub Pages, this would be https://<username>.github.io
  url: 'https://janlahmann.github.io',
  // Set the /<baseUrl>/ pathname under which your site is served
  baseUrl: '/doQumentation/',

  // GitHub pages deployment config
  organizationName: 'JanLahmann',
  projectName: 'doQumentation',
  trailingSlash: false,

  onBrokenLinks: 'warn',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  // Enable Thebe for Jupyter execution
  scripts: [
    {
      src: 'https://unpkg.com/thebe@0.9.2/lib/index.js',
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
      title: 'RasQberry Tutorials',
      logo: {
        alt: 'RasQberry Logo',
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
          href: '/jupyter-settings',
          label: '⚙️ Jupyter',
          position: 'right',
        },
        {
          href: 'https://github.com/JanLahmann/doQumentation',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Tutorials',
          items: [
            {
              label: 'Get Started',
              to: '/tutorials/hello-world',
            },
          ],
        },
        {
          title: 'Community',
          items: [
            {
              label: 'RasQberry GitHub',
              href: 'https://github.com/JanLahmann/RasQberry-Two',
            },
            {
              label: 'Qiskit Slack',
              href: 'https://qisk.it/join-slack',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'IBM Quantum',
              href: 'https://quantum.ibm.com',
            },
            {
              label: 'Qiskit Documentation',
              href: 'https://docs.quantum.ibm.com',
            },
          ],
        },
      ],
      copyright: `Tutorial content © IBM Corp. Site built for RasQberry.`,
    },
    
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['python', 'bash', 'json'],
    },

    // Custom config for Jupyter integration
    // This is read by our ExecutableCode component
    customFields: {
      jupyter: {
        // Default Jupyter server URL (overridden at runtime)
        defaultUrl: 'http://localhost:8888',
        defaultToken: 'rasqberry',
        // Binder URL for GitHub Pages fallback
        binderUrl: 'https://mybinder.org/v2/gh/Qiskit/documentation/HEAD',
      },
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
