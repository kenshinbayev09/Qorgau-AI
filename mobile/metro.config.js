// Metro: разрешаем .wasm (нужно для SQLite в браузере, expo-sqlite web)
const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);
config.resolver.assetExts.push('wasm');

module.exports = config;
