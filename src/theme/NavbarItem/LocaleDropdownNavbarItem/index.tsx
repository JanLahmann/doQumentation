/**
 * Swizzled LocaleDropdownNavbarItem — wraps the original to filter
 * which locales appear in the dropdown based on customFields.visibleLocales.
 *
 * All locales remain built and deployed; this only controls UI visibility.
 * The current locale is always shown so users on "hidden" locales can navigate.
 */

import React, {type ReactNode} from 'react';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import {useAlternatePageUtils} from '@docusaurus/theme-common/internal';
import {translate} from '@docusaurus/Translate';
import {mergeSearchStrings, useHistorySelector} from '@docusaurus/theme-common';
import DropdownNavbarItem from '@theme/NavbarItem/DropdownNavbarItem';
import IconLanguage from '@theme/Icon/Language';
import type {LinkLikeNavbarItemProps} from '@theme/NavbarItem';
import type {Props} from '@theme/NavbarItem/LocaleDropdownNavbarItem';

function useLocaleDropdownUtils() {
  const {
    siteConfig,
    i18n: {localeConfigs},
  } = useDocusaurusContext();
  const alternatePageUtils = useAlternatePageUtils();
  const search = useHistorySelector((history) => history.location.search);
  const hash = useHistorySelector((history) => history.location.hash);

  const getLocaleConfig = (locale: string) => {
    const localeConfig = localeConfigs[locale];
    if (!localeConfig) {
      throw new Error(
        `Docusaurus bug, no locale config found for locale=${locale}`,
      );
    }
    return localeConfig;
  };

  const getBaseURLForLocale = (locale: string) => {
    const localeConfig = getLocaleConfig(locale);
    const isSameDomain = localeConfig.url === siteConfig.url;
    if (isSameDomain) {
      return `pathname://${alternatePageUtils.createUrl({
        locale,
        fullyQualified: false,
      })}`;
    }
    return alternatePageUtils.createUrl({
      locale,
      fullyQualified: true,
    });
  };

  return {
    getURL: (locale: string, options: {queryString: string | undefined}) => {
      const finalSearch = mergeSearchStrings(
        [search, options.queryString],
        'append',
      );
      return `${getBaseURLForLocale(locale)}${finalSearch}${hash}`;
    },
    getLabel: (locale: string) => {
      return getLocaleConfig(locale).label;
    },
    getLang: (locale: string) => {
      return getLocaleConfig(locale).htmlLang;
    },
  };
}

export default function LocaleDropdownNavbarItem({
  mobile,
  dropdownItemsBefore,
  dropdownItemsAfter,
  queryString,
  ...props
}: Props): ReactNode {
  const utils = useLocaleDropdownUtils();

  const {
    siteConfig,
    i18n: {currentLocale, locales},
  } = useDocusaurusContext();

  // Filter locales to only those in visibleLocales (always include current)
  const visibleLocales = siteConfig.customFields?.visibleLocales as
    | string[]
    | undefined;
  const filteredLocales = visibleLocales
    ? locales.filter(
        (l) => visibleLocales.includes(l) || l === currentLocale,
      )
    : locales;

  const localeItems = filteredLocales.map(
    (locale): LinkLikeNavbarItemProps => {
      return {
        label: utils.getLabel(locale),
        lang: utils.getLang(locale),
        to: utils.getURL(locale, {queryString}),
        target: '_self',
        autoAddBaseUrl: false,
        className:
          locale === currentLocale
            ? mobile
              ? 'menu__link--active'
              : 'dropdown__link--active'
            : '',
      };
    },
  );

  // On non-English pages, add a prominent "View in English" item at the top
  const viewInEnglishItem: LinkLikeNavbarItemProps[] =
    currentLocale !== 'en'
      ? [
          {
            label: `\u{1F1EC}\u{1F1E7} ${translate({
              message: 'View in English',
              id: 'theme.navbar.viewInEnglish',
              description: 'Label for the View in English link shown on translated pages',
            })}`,
            lang: utils.getLang('en'),
            to: utils.getURL('en', {queryString}),
            target: '_self',
            autoAddBaseUrl: false,
            className: 'dropdown__link--view-english',
          },
        ]
      : [];

  const items = [...viewInEnglishItem, ...dropdownItemsBefore, ...localeItems, ...dropdownItemsAfter];

  const dropdownLabel = mobile
    ? translate({
        message: 'Languages',
        id: 'theme.navbar.mobileLanguageDropdown.label',
        description: 'The label for the mobile language switcher dropdown',
      })
    : utils.getLabel(currentLocale);

  return (
    <DropdownNavbarItem
      {...props}
      mobile={mobile}
      label={
        <>
          <IconLanguage />
          {dropdownLabel}
        </>
      }
      items={items}
    />
  );
}
