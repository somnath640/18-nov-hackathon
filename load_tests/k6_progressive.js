import http from 'k6/http';
import { check, sleep } from 'k6';

const tier = __ENV.TIER || '5k';
const vus = tier === '50k' ? 50000 : tier === '10k' ? 10000 : 5000;

export const options = {
  stages: [
    { duration: '2m', target: Math.min(vus, 10000) },
    { duration: '3m', target: vus },
    { duration: '5m', target: vus },
    { duration: '2m', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(50)<240', 'p(95)<450', 'p(99)<590'],
    http_req_failed: ['rate<0.0005'],
  },
};

export default function () {
  const vuId = __VU;
  const tenant = `tenant_${vuId % 50}`;
  const payload = JSON.stringify({
    tenant_id: tenant,
    user_id: `user_${vuId}`,
    query: 'Verify batch LOT-88392 safety protocol and return triage status',
  });
  const response = http.post(
    __ENV.BASE_URL || 'http://localhost:8000/api/v1/agent/query',
    payload,
    { headers: { 'Content-Type': 'application/json' } },
  );
  check(response, {
    'status is 200': (r) => r.status === 200,
    'tenant is retained': (r) => r.json('tenant_id') === tenant,
  });
  sleep(1);
}
