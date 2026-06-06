/**
 * Demo target project entry point.
 * This project is missing a utils module — that's what AetherFusion will detect.
 */

// Note: no utils module exists — this is intentional for demo purposes.
// AetherFusion will scan and identify utils as a fusible candidate from demo-source.

export function hello(name: string): string {
  return `Hello, ${name}! Welcome to the target project.`;
}

export function add(a: number, b: number): number {
  return a + b;
}