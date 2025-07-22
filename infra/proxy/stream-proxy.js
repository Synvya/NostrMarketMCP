import http from 'http';
import fetch from 'node-fetch';

const API_KEY = process.env.API_KEY;
const UPSTREAM_BASE = process.env.UPSTREAM_URL || 'https://api.synvya.com';

const server = http.createServer(async (req, res) => {
    const rawUrl = req.url || '/';
    const url = rawUrl.startsWith('/proxy/') ? rawUrl.slice('/proxy'.length) : rawUrl;

    // Health checks (both raw and /proxy/ prefixed)
    if (rawUrl === '/health' || rawUrl === '/proxy/health' || url === '/health') {
        res.writeHead(200, { 'content-type': 'text/plain' });
        return res.end('ok');
    }

    if (req.method === 'POST' && url.startsWith('/api/')) {
        res.writeHead(200, {
            'content-type': 'text/event-stream',
            'cache-control': 'no-cache',
            'connection': 'keep-alive'
        });

        const chunks = [];
        req.on('data', c => chunks.push(c));
        req.on('end', async () => {
            try {
                const upstream = await fetch(UPSTREAM_BASE + url, {
                    method: 'POST',
                    headers: {
                        'content-type': 'application/json',
                        'x-api-key': API_KEY
                    },
                    body: Buffer.concat(chunks)
                });

                if (!upstream.ok || !upstream.body) {
                    res.write(`data: ${JSON.stringify({ error: upstream.statusText })}\n\n`);
                    return res.end();
                }

                res.flushHeaders?.();
                for await (const chunk of upstream.body) {
                    res.write(chunk);
                }
                res.end();
            } catch (e) {
                res.write(`data: ${JSON.stringify({ error: e.message })}\n\n`);
                res.end();
            }
        });
        return;
    }

    res.writeHead(404);
    res.end();
});

server.listen(process.env.PORT || 8080, () => {
    console.log('proxy listening on', process.env.PORT || 8080);
});