exports.handler = async (event) => {
    if (event.httpMethod !== 'POST') {
        return { statusCode: 405, body: 'Method Not Allowed' };
    }

    try {
        const data = JSON.parse(event.body);
        
        const leadId = crypto.randomUUID();
        const now = new Date().toISOString();
        const materials = JSON.stringify(data.materials || []);
        const tags = JSON.stringify(inferTags(data.materials || []));
        const inspection = data.materials && data.materials.includes('Request a Private Inspection') ? 1 : 0;
        const marketing = data.materials && data.materials.includes('WTC Abuja Updates & Private Invitations') ? 1 : 0;
        
        // Escape single quotes
        const esc = (s) => (s || '').replace(/'/g, "''");
        
        const sql = `INSERT INTO leads(id,first_name,last_name,email,phone,company,job_title,timing,materials,tags,inspection,marketing,campaign,device_id,submitted,source)
        VALUES('${leadId}','${esc(data.first_name)}','${esc(data.last_name)}','${esc(data.email)}','${esc(data.phone)}','${esc(data.company)}','${esc(data.job_title || '')}','${esc(data.timing || '')}','${materials}','${tags}',${inspection},${marketing},'NOG Energy Week 2026','mobile-qr','${now}','qr_mobile_landing')`;
        
        // Send to Turso
        const tursoUrl = process.env.TURSO_URL.replace('libsql://', 'https://') + '/v2/pipeline';
        
        const response = await fetch(tursoUrl, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${process.env.TURSO_TOKEN}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                requests: [{ type: 'execute', stmt: { sql } }]
            })
        });
        
        if (response.ok) {
            return {
                statusCode: 200,
                body: JSON.stringify({ success: true, message: 'Lead saved' })
            };
        } else {
            return {
                statusCode: 500,
                body: JSON.stringify({ success: false, message: 'Database error' })
            };
        }
    } catch (error) {
        return {
            statusCode: 500,
            body: JSON.stringify({ success: false, message: error.message })
        };
    }
};

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