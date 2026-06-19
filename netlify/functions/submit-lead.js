const https = require('https');

exports.handler = async (event) => {
    if (event.httpMethod !== 'POST') {
        return { statusCode: 405, body: JSON.stringify({ error: 'Method Not Allowed' }) };
    }

    try {
        const data = JSON.parse(event.body);
        
        const leadId = generateUUID();
        const now = new Date().toISOString();
        const materials = JSON.stringify(data.materials || []);
        const tags = JSON.stringify(inferTags(data.materials || []));
        const inspection = data.materials && data.materials.includes('Request a Private Inspection') ? 1 : 0;
        const marketing = data.materials && data.materials.includes('WTC Abuja Updates & Private Invitations') ? 1 : 0;
        
        const esc = (s) => (s || '').replace(/'/g, "''");
        
        const sql = `INSERT INTO leads(id,first_name,last_name,email,phone,company,job_title,timing,materials,tags,inspection,marketing,campaign,device_id,submitted,source)
        VALUES('${leadId}','${esc(data.first_name)}','${esc(data.last_name)}','${esc(data.email)}','${esc(data.phone)}','${esc(data.company)}','${esc(data.job_title || '')}','${esc(data.timing || '')}','${materials}','${tags}',${inspection},${marketing},'NOG Energy Week 2026','mobile-qr','${now}','qr_mobile_landing')`;
        
        const tursoHost = process.env.TURSO_URL.replace('libsql://', '');
        
        const result = await tursoRequest(tursoHost, process.env.TURSO_TOKEN, sql);
        
        return {
            statusCode: 200,
            body: JSON.stringify({ success: true })
        };
    } catch (error) {
        console.error('Error:', error);
        return {
            statusCode: 200,
            body: JSON.stringify({ success: true })
        };
    }
};

function tursoRequest(host, token, sql) {
    return new Promise((resolve, reject) => {
        const body = JSON.stringify({
            requests: [{ type: 'execute', stmt: { sql } }]
        });
        
        const options = {
            hostname: host,
            path: '/v2/pipeline',
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(body)
            },
            timeout: 10000
        };
        
        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => resolve(JSON.parse(data)));
        });
        
        req.on('error', (e) => reject(e));
        req.write(body);
        req.end();
    });
}

function inferTags(materials) {
    const mapping = {
        'Office Floorplates': 'Office Leasing',
        'Corporate Prospectus': 'Office Leasing',
        'Residence Floorplans': 'Executive Residences',
        'Security & Continuity Brief': 'Security & Continuity',
        'Clubhouse Overview': 'Clubhouse',
        'Location Overview': 'Location',
        'Request a Private Inspection': 'Private Inspection',
        'WTC Abuja Updates & Private Invitations': 'Newsletter'
    };
    return [...new Set(materials.map(m => mapping[m] || m))];
}

function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}