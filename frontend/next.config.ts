import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["192.168.100.178"],
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
