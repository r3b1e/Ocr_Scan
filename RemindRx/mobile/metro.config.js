const path = require('path');
const { getDefaultConfig, mergeConfig } = require('@react-native/metro-config');

const shared = path.resolve(__dirname, '../shared');

/**
 * Metro configuration. `../shared` holds the medication logic used by both
 * this app and the website, so Metro watches it and resolves its imports from
 * this app's node_modules.
 *
 * @type {import('@react-native/metro-config').MetroConfig}
 */
const config = {
  watchFolders: [shared],
  resolver: {
    nodeModulesPaths: [path.resolve(__dirname, 'node_modules')],
    blockList: [/shared\/node_modules\/.*/],
    // `@shared/x` → ../shared/x (same alias as tsconfig paths).
    resolveRequest: (context, moduleName, platform) =>
      context.resolveRequest(
        context,
        moduleName.startsWith('@shared/') ? path.join(shared, moduleName.slice('@shared/'.length)) : moduleName,
        platform,
      ),
  },
};

module.exports = mergeConfig(getDefaultConfig(__dirname), config);
