// Static demo build (VITE_STATIC=1): no sign-in and no backend. Pages read real API responses captured from the
// deployed system by pipelines/deploy/snapshot_demo.py, so the demo keeps working after the AWS stacks are gone.
export const STATIC = import.meta.env.VITE_STATIC === '1';

type Meta = { captured_at: string; run_id: string; scenario_id: string; work_order_id: string; assigned_to: string | null };
const found = import.meta.glob<Meta>('../static-demo/snapshot/meta.json', { eager: true, import: 'default' });
export const SNAPSHOT: Meta | null = STATIC ? Object.values(found)[0] ?? null : null;
