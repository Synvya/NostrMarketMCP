import fetch from 'node-fetch';

/**
 * Lambda proxy handler using native response streaming (ESM).
 */
export const handler = async (event) => {
    const stream = event.responseStream;

    stream.setContentType('text/event-stream');
    stream.write('data: Proxy starting...\n\n');

    const upstream = await fetch('https://api.synvya.com/api/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-API-Key': process.env.SYNVYA_API_KEY,
        },
        body: event.body,
    });

    if (!upstream.ok || !upstream.body) {
        stream.write(`data: ${JSON.stringify({ error: upstream.statusText })}\n\n`);
        return stream.end();
    }

    for await (const chunk of upstream.body) {
        stream.write(chunk);
    }

    stream.end();
};