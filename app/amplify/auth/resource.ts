import { defineAuth } from '@aws-amplify/backend';

/**
 * Cognito user pool for Uptime Desk. Email sign-in, two groups. The technician's roster id
 * (config/technicians.yaml) is stored in custom:technician_id; the API and MCP tools read it
 * from the token, never from the request body. Users are created by scripts/seed-users.sh.
 */
export const auth = defineAuth({
  loginWith: { email: true },
  groups: ['manager', 'technician'],
  userAttributes: {
    'custom:technician_id': { dataType: 'String', mutable: true, maxLen: 8 },
  },
});
