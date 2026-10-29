// Local stylesheet refresh only. No external requests or page reloads.
const themeLink = document.getElementById('theme-palette');
setInterval(() => {
  if (document.visibilityState === 'visible' && themeLink) {
    themeLink.href = '/theme.css?t=' + Date.now();
  }
}, 5000);
