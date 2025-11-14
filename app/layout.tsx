import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Prokerala Astrology Report",
  description:
    "Generate natal chart and transit insights powered by the Prokerala Astrology API with AI commentary.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <main>{children}</main>
      </body>
    </html>
  );
}
