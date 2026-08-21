async (page) => {
  await page.evaluate(([acc, ref]) => {
    localStorage.setItem('lms.accessToken', acc);
    localStorage.setItem('lms.refreshToken', ref);
  }, ['eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmYjQ5M2VkZi0zNDMzLTQ1MTYtOWI0Ni1jYTA2ODhhM2Q1YjciLCJ0b2tlbl90eXBlIjoiYWNjZXNzIiwib3JnX2lkIjoiODViYzhjZmUtMTMxNS00ZGZmLTkzNWMtMThhODhhODhlYzRlIiwicm9sZSI6Ik9XTkVSIiwiaWF0IjoxNzg2MjE5Mzg1LCJleHAiOjE3ODYyMjExODV9._0jLo4_D1KewHAvwQxMblJitftJC1lXtPUOgyskLeP0', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmYjQ5M2VkZi0zNDMzLTQ1MTYtOWI0Ni1jYTA2ODhhM2Q1YjciLCJ0b2tlbl90eXBlIjoicmVmcmVzaCIsIm9yZ19pZCI6Ijg1YmM4Y2ZlLTEzMTUtNGRmZi05MzVjLTE4YTg4YTg4ZWM0ZSIsInJvbGUiOiJPV05FUiIsImlhdCI6MTc4NjIxOTM4NSwiZXhwIjoxNzg2ODI0MTg1fQ.Gzh-7d62hkQKojIZPr2PCf5n6YZV826Imu4F1CZUORo']);
  await page.goto('http://localhost:3113/media');
  await page.waitForTimeout(2500);
  return await page.url();
}
