#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { FoundationStack } from '../lib/foundation-stack';
import { DemoStack } from '../lib/demo-stack';

// Region is us-east-2: the org SCP denies regional services in us-west-2 and us-east-1.
const app = new cdk.App();
const env = { account: app.node.tryGetContext('account'), region: app.node.tryGetContext('region') };
const profile = app.node.tryGetContext('profile');
if (profile !== 'idle' && profile !== 'demo') {
  throw new Error(`context "profile" must be idle or demo, got ${profile}`);
}

const foundation = new FoundationStack(app, 'UptimeDesk-Foundation', { env });
// The foundation is always on, so it always carries the idle tag, whichever profile is deploying.
cdk.Tags.of(foundation).add('cost-profile', 'idle');

// The demo stack exists only while the demo profile is active; demo-down.sh destroys it.
if (profile === 'demo') {
  const demo = new DemoStack(app, 'UptimeDesk-Demo', { env, foundation });
  cdk.Tags.of(demo).add('cost-profile', 'demo');
}

cdk.Tags.of(app).add('project', 'uptime-desk');
