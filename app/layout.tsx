import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Sheetwise — Explore your data',
  description: 'Turn a spreadsheet into a dashboard. Ask questions and explore answers grounded in your data.',
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
