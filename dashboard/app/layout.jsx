import Script from "next/script";

import PolicyEngineFooter from "../src/components/PolicyEngineFooter";
import PolicyEngineHeader from "../src/components/PolicyEngineHeader";

import "./globals.css";

export const metadata = {
  title: "Employer NICs exemption for young workers (18-24) | PolicyEngine",
  description:
    "Interactive dashboard estimating the fiscal cost and employment effects of extending the employer NICs zero rate to all employees aged 18 to 24, using PolicyEngine UK microsimulation.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <PolicyEngineHeader />
        {children}
        <PolicyEngineFooter />
        {/* Google Analytics: policyengine.org's GA4 property; this app is served at
            policyengine.org/uk/young-worker-nics through a rewrite, where the main site's GA does not reach. */}
        {process.env.NODE_ENV === "production" && (
          <>
            <Script
              src="https://www.googletagmanager.com/gtag/js?id=G-2YHG89FY0N"
              strategy="afterInteractive"
            />
            <Script id="google-analytics" strategy="afterInteractive">
              {`window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', 'G-2YHG89FY0N');`}
            </Script>
          </>
        )}
      </body>
    </html>
  );
}
