export const environment = {
  production: true,
  orchestratorBaseUrl: 'http://localhost:8000',
  chatEndpoint: '/chat',
  streamEndpoint: '/chat/stream',
  agentName: 'SAPE',
  agentTagline: 'Sistema Agéntico para Postulación y Entrevistas',
  agentAvatarInitials: 'S',
  transportMode: 'sse' as 'sse' | 'polling',
  pollingIntervalMs: 1000,
  requestTimeoutMs: 120000,
};
