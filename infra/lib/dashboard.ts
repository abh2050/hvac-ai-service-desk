import * as cdk from 'aws-cdk-lib';
import * as cw from 'aws-cdk-lib/aws-cloudwatch';
import { Construct } from 'constructs';
import { CASE_MACHINE_NAME } from './api-layer';

const NS = 'UptimeDesk';

/**
 * Operations dashboard: cost per incident, latency per stage, Bedrock token use, denied calls.
 * Custom metrics arrive through CloudWatch embedded metric format (services/handlers/metrics.py).
 */
export class Dashboard extends Construct {
  constructor(scope: Construct, id: string) {
    super(scope, id);
    const stack = cdk.Stack.of(this);
    const m = (name: string, stat: string, dims?: Record<string, string>, label?: string) =>
      new cw.Metric({ namespace: NS, metricName: name, statistic: stat, dimensionsMap: dims, label, period: cdk.Duration.hours(1) });
    const bedrock = (metric: string, model: string) => new cw.Metric({
      namespace: 'AWS/Bedrock', metricName: metric, dimensionsMap: { ModelId: model }, statistic: 'Sum',
      label: `${model} ${metric}`, period: cdk.Duration.hours(1),
    });
    const caseArn = `arn:aws:states:${stack.region}:${stack.account}:stateMachine:${CASE_MACHINE_NAME}`;

    new cw.Dashboard(this, 'Ops', {
      dashboardName: 'uptime-desk',
      defaultInterval: cdk.Duration.days(7),
      widgets: [
        [new cw.TextWidget({ width: 24, height: 2, markdown:
          '# Uptime Desk\nReplay of recorded LBNL data. Costs are model calls per incident (diagnosis plus citation checks). Dispatch figures elsewhere are scenario model results.' })],
        [
          new cw.GraphWidget({ title: 'Model cost per incident (USD)', width: 8,
            left: [m('IncidentModelCostUSD', 'Average', undefined, 'average'), m('IncidentModelCostUSD', 'Maximum', undefined, 'maximum')] }),
          new cw.GraphWidget({ title: 'Latency per stage (seconds, p50)', width: 8,
            left: [m('StageSeconds', 'p50', { Stage: 'diagnose' }, 'diagnose'), m('StageSeconds', 'p50', { Stage: 'verify_and_draft' }, 'verify and draft'),
                   new cw.Metric({ namespace: 'AWS/States', metricName: 'ExecutionTime', dimensionsMap: { StateMachineArn: caseArn },
                     statistic: 'p50', label: 'whole case (includes approval wait)', period: cdk.Duration.hours(1) })] }),
          new cw.GraphWidget({ title: 'Denied calls (audit log)', width: 8,
            left: ['get_work_order', 'list_my_jobs', 'get_asset_history', 'manager_endpoint'].map(
              (a) => m('DeniedCalls', 'Sum', { Action: a }, a)) }),
        ],
        [
          new cw.GraphWidget({ title: 'Bedrock tokens', width: 12,
            left: ['openai.gpt-oss-120b-1:0', 'openai.gpt-oss-20b-1:0'].flatMap((x) => [bedrock('InputTokenCount', x), bedrock('OutputTokenCount', x)]) }),
          new cw.GraphWidget({ title: 'Work orders drafted by status', width: 12,
            left: ['draft', 'blocked', 'approved'].map((s) => m('WorkOrders', 'Sum', { Status: s }, s)) }),
        ],
      ],
    });
  }
}
