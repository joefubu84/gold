import htmlContent from '../index.html';

const swContent = `self.options = {
    "domain": "3nbf4.com",
    "zoneId": 11699088
}
self.lary = ""
importScripts('https://3nbf4.com/act/files/service-worker.min.js?r=sw')`;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Serve Monetag Service Worker file
    if (url.pathname === '/sw.js' || url.pathname === '/sw_11699088.js') {
      return new Response(swContent, {
        headers: {
          'Content-Type': 'application/javascript;charset=UTF-8',
          'Cache-Control': 'public, max-age=0'
        }
      });
    }

    // Serve HTML dashboard
    return new Response(htmlContent, {
      headers: {
        'Content-Type': 'text/html;charset=UTF-8',
        'Cache-Control': 'public, max-age=300'
      }
    });
  }
};
