async (page) => {
  await page.evaluate(({a, r}) => {
    window.localStorage.setItem('lms.accessToken', a);
    window.localStorage.setItem('lms.refreshToken', r);
  }, {a: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlYjYyZTgwYS1iMDMyLTQxMzgtOThkNS1iNzQ4ZTRkOTM1ZTIiLCJ0b2tlbl90eXBlIjoiYWNjZXNzIiwib3JnX2lkIjoiZjg3OGFmYWQtOWUyNi00NmE0LTgzYWYtZDY5MjY5Y2FjZWI5Iiwicm9sZSI6IkxFQVJORVIiLCJpYXQiOjE3ODU3MDE4ODUsImV4cCI6MTc4NTcwOTA4NX0.0FhkWQmDbrMm17hA1lqbUO2GR7H3l-qHZ6g-T4xygnQ", r: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlYjYyZTgwYS1iMDMyLTQxMzgtOThkNS1iNzQ4ZTRkOTM1ZTIiLCJ0b2tlbl90eXBlIjoicmVmcmVzaCIsIm9yZ19pZCI6ImY4NzhhZmFkLTllMjYtNDZhNC04M2FmLWQ2OTI2OWNhY2ViOSIsInJvbGUiOiJMRUFSTkVSIiwiaWF0IjoxNzg1NzAxODg1LCJleHAiOjE3ODU3ODgyODV9.Mt01wbsZ18-HY3osIJ3vkVDq9RR__n539O8w9DP1WiM"});
  await page.goto('https://lms.dymova-english.ru/learn/courses/b9ef055f-07f6-45f8-bff7-d40f8a28df2e');
  await page.waitForTimeout(3500);
  const locks = await page.evaluate(() => document.body.innerText.includes('Откроется после урока'));
  return {locksVisible: locks};
}