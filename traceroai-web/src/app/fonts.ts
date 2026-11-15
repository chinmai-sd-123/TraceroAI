import { IBM_Plex_Mono, Public_Sans } from "next/font/google";

// Public Sans, the typeface of US government reports, carries TraceroAI's
// report voice; Plex Mono sets ids, sources, scores and code. The root layout
// puts these variables on <html>; globals.css points the font tokens at them.
export const publicSans = Public_Sans({ subsets: ["latin"], variable: "--font-public-sans" });
export const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
});

export const fontVariables = `${publicSans.variable} ${plexMono.variable}`;
