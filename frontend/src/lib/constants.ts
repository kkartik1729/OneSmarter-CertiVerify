/**
 * Application-wide configuration and external links.
 */

export interface SocialLink {
  id: 'instagram' | 'facebook' | 'website';
  name: string;
  url: string;
  ariaLabel: string;
}

/**
 * Official social media and company links for OneSmarter Inc.
 */
export const SOCIAL_LINKS: SocialLink[] = [
  {
    id: 'instagram',
    name: 'Instagram',
    url: 'https://www.instagram.com/onesmarter.inc/',
    ariaLabel: 'Visit OneSmarter on Instagram (opens in new tab)',
  },
  {
    id: 'facebook',
    name: 'Facebook',
    url: 'https://www.facebook.com/Onesmarter.Inc/',
    ariaLabel: 'Visit OneSmarter on Facebook (opens in new tab)',
  },
  {
    id: 'website',
    name: 'Company Website',
    url: 'https://www.onesmarter.com/',
    ariaLabel: 'Visit OneSmarter official website (opens in new tab)',
  },
];
