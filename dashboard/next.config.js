/** @type {import('next').NextConfig} */
const BASE_PATH = "/uk/young-worker-nics";

const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@policyengine/design-system"],
  // Mounted as a Next.js multizone under policyengine.org/uk/young-worker-nics,
  // so pages and /_next assets must resolve under that path prefix.
  basePath: BASE_PATH,
  // Exposed so raw fetch() and plain <img> tags — which Next.js does not
  // auto-prefix under basePath — can build their own absolute URLs.
  env: { NEXT_PUBLIC_BASE_PATH: BASE_PATH },
};

module.exports = nextConfig;
