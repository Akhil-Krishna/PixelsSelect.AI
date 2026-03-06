import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://localhost:8000/api/v1/:path*',
      },
    ];
  },
  allowedDevOrigins: ['127.0.0.1', 'localhost'],
  experimental: {
    middlewareClientMaxBodySize: 524288000,
  },
};

export default nextConfig;

