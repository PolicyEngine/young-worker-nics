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
      </body>
    </html>
  );
}
