const awslambda = require('@aws/awslambda');
const fetch = require('node-fetch');

exports.handler = awslambda.streamifyResponse(
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
            stream.write(chunk);
        }

        stream.end();
    }
);