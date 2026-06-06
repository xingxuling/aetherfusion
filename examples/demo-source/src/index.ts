/**
 * Demo source project entry point.
 */

import { clamp, lerp } from './utils/math';
import { capitalize, slugify } from './utils/strings';

export function greet(name: string): string {
  return `Hello, ${capitalize(name)}!`;
}

export function formatSlug(title: string): string {
  return slugify(title);
}

export function scaleValue(val: number): number {
  return clamp(lerp(0, 100, val / 10), 0, 100);
}