import type { NextConfig } from "next";
import path from "path";
import CopyWebpackPlugin from "copy-webpack-plugin";

const nextConfig: NextConfig = {
  webpack: (config, { dev, isServer, webpack }) => {
    if (!isServer) {
      // Copy Cesium Assets
      config.plugins.push(
        new CopyWebpackPlugin({
          patterns: [
            {
              from: path.join(
                process.cwd(),
                "node_modules/cesium/Build/Cesium/Workers"
              ),
              to: "../public/cesium/Workers",
              info: { minimized: true },
            },
            {
              from: path.join(
                process.cwd(),
                "node_modules/cesium/Build/Cesium/ThirdParty"
              ),
              to: "../public/cesium/ThirdParty",
              info: { minimized: true },
            },
            {
              from: path.join(
                process.cwd(),
                "node_modules/cesium/Build/Cesium/Assets"
              ),
              to: "../public/cesium/Assets",
              info: { minimized: true },
            },
            {
              from: path.join(
                process.cwd(),
                "node_modules/cesium/Build/Cesium/Widgets"
              ),
              to: "../public/cesium/Widgets",
              info: { minimized: true },
            },
          ],
        })
      );

      // Define Cesium base URL
      config.plugins.push(
        new webpack.DefinePlugin({
          CESIUM_BASE_URL: JSON.stringify("/cesium"),
        })
      );
    }

    if (!dev && !isServer) {
      config.optimization = {
        ...config.optimization,
        moduleIds: 'deterministic',
        splitChunks: {
          chunks: 'all',
          cacheGroups: {
            default: false,
            vendors: false,
            cesium: {
              name: 'cesium',
              test: /[\\/]node_modules[\\/]cesium[\\/]/,
              priority: 30,
              reuseExistingChunk: true,
            },
            vendor: {
              name: 'vendor',
              chunks: 'all',
              test: /node_modules/,
              priority: 20
            },
            common: {
              name: 'common',
              minChunks: 2,
              chunks: 'all',
              priority: 10,
              reuseExistingChunk: true,
              enforce: true
            }
          }
        }
      };
    }
    return config;
  },
  transpilePackages: ['cesium', 'resium'],
};

export default nextConfig;
