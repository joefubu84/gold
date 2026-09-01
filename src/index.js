import htmlContent from '../index.html';

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Optional API endpoint for dynamic stats if requested
    if (url.pathname === '/api/stats') {
      return new Response(JSON.stringify({
        status: 'success',
        timestamp: new Date().toISOString(),
        assets: {
          xauusd: { price: 4448.20, changePct: 1.42, trend: 'Strong Bullish' },
          dxy: { price: 98.85, changePct: -0.38, trend: 'Bearish Pressure' },
          eurusd: { price: 1.1582, changePct: 0.31, trend: 'Moderate Bullish' }
        },
        stance: 'BULLISH',
        confidence: 88
      }), {
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        }
      });
    }

    // Serve the investment terminal UI
    return new Response(htmlContent, {
      headers: {
        'Content-Type': 'text/html;charset=UTF-8',
        'Cache-Control': 'public, max-age=300'
      }
    });
  }
};
