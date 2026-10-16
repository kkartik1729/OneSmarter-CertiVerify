/**
 * Application-wide configuration and external links.
 */

export interface SocialLink {
  id: 'instagram' | 'x' | 'facebook' | 'website';
  name: string;
  url: string;
  ariaLabel: string;
  isPlaceholder?: boolean;
}

/**
 * Central configuration for social media and company links.
 * Verified official company website: https://onesmarter.com
 * Social channels without confirmed handles use configurable placeholders.
 */
export const SOCIAL_LINKS: SocialLink[] = [
  {
    id: 'instagram',
    name: 'Instagram',
    url: 'https://instagram.com/onesmarter_placeholder',
    ariaLabel: 'Visit OneSmarter on Instagram (opens in new tab)',
    isPlaceholder: true,
  },
  {
    id: 'x',
    name: 'X (formerly Twitter)',
    url: 'https://x.com/onesmarter_placeholder',
    ariaLabel: 'Visit OneSmarter on X formerly Twitter (opens in new tab)',
    isPlaceholder: true,
  },
  {
    id: 'facebook',
    name: 'Facebook',
    url: 'https://facebook.com/onesmarter_placeholder',
    ariaLabel: 'Visit OneSmarter on Facebook (opens in new tab)',
    isPlaceholder: true,
  },
  {
    id: 'website',
    name: 'OneSmarter Website',
    url: 'https://onesmarter.com',
    ariaLabel: 'Visit OneSmarter official company website (opens in new tab)',
    isPlaceholder: false,
  },
];
