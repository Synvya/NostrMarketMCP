import awslambda from '@aws/awslambda';
import fetch from 'node-fetch';

export const handler = awslambda.streamifyResponse(
    async (event, stream) => {
        stream.setHeader('Content-Type', 'text/event-stream');
        stream.setHeader('Access-Control-Allow-Origin', '*');
        stream.setHeader('Cache-Control', 'no-cache');

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
            stream.write(chunk);           // pass every SSE line through
        }
        stream.end();
    }
);