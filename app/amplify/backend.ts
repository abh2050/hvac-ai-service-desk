import { defineBackend } from '@aws-amplify/backend';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { auth } from './auth/resource';

const backend = defineBackend({ auth });

// Publish the pool ids for the CDK backend (infra/), which reads them from SSM.
const stack = backend.createStack('UptimeDeskParams');
const pool = backend.auth.resources.userPool;
const client = backend.auth.resources.userPoolClient;
new ssm.StringParameter(stack, 'PoolId', { parameterName: '/uptime-desk/cognito/user-pool-id', stringValue: pool.userPoolId });
new ssm.StringParameter(stack, 'ClientId', { parameterName: '/uptime-desk/cognito/client-id', stringValue: client.userPoolClientId });
