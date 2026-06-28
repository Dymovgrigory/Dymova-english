module.exports = {
  testEnvironment: 'jsdom',
  testMatch: ['**/tests/js/**/*.test.js'],
  collectCoverageFrom: [
    'prototype/**/*.js',
    '!prototype/tilda_blocks_min/**',
  ],
};
