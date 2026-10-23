import fs from 'node:fs';

const scenes = [
  {seconds: 12, text: 'An air handler starts drifting in a critical building. The alarm is easy. The hard question is what failed, which instructions are safe, and who can reach it before the service window closes.'},
  {seconds: 12.2, text: 'Sensor trends sit in one system. Equipment manuals sit in another. Dispatch rules live in spreadsheets and experience. Each handoff creates another place for evidence or time to disappear.'},
  {seconds: 31.5, text: 'Uptime Desk joins that path on AWS. Recorded LBNL data streams through Kinesis. Rules stay primary while XGBoost supplies a second opinion. Bedrock proposes a diagnosis from manual pages, then a second model verifies each quotation. PostgreSQL rejects unverified steps. Step Functions waits for a manager, then OR-Tools assigns a qualified technician. Cognito and the MCP gateway bind requests to a verified identity.'},
  {seconds: 58, text: "The manager launches a recorded field scenario and watches each stage complete. The diagnosis shows rules, model, and disagreement. Every accepted check opens the source manual at the cited page. The manager keeps control: approve the draft, remove an optional step, or reject it with a reason. Approval resumes the case machine. The dispatch board shows the selected technician, a runner-up, travel, lateness, and rationale. The assistant can list that technician's jobs and answer from verified passages. A request for another technician's order is denied and audited. A passing hosted run reached a draft in a median 39.4 seconds and dispatch in 77.3. If the case has no sourced lockout step, the pipeline stops. In the hosted batch, that policy blocked 2 of 10 runs instead of sending unsupported work."},
  {seconds: 28.2, text: 'The measured results keep their boundaries. On lab air handlers, model recall was 0.957 against 0.739 for rules. Rules won on the lab economizer and field RTU. Citation support was 0.880 against 0.122. In the dispatch scenario, OR-Tools cut lateness from 1,343 to 402 minutes against nearest qualified, while earliest available also reached 402.'},
  {seconds: 8.1, text: "Explore the recorded demo, inspect every gate report on GitHub, and see the rest of Abhishek Shah's work in the linked portfolio."},
];

const stamp = (seconds) => {
  const ms = Math.round(seconds * 1000);
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  const rem = ms % 1000;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(rem).padStart(3, '0')}`;
};

let cursor = 0;
let index = 1;
const output = [];
for (const scene of scenes) {
  const words = scene.text.split(/\s+/);
  const chunks = [];
  for (let i = 0; i < words.length; i += 9) chunks.push(words.slice(i, i + 9).join(' '));
  const step = scene.seconds / chunks.length;
  chunks.forEach((chunk, i) => {
    output.push(`${index++}\n${stamp(cursor + i * step)} --> ${stamp(cursor + (i + 1) * step)}\n${chunk}\n`);
  });
  cursor += scene.seconds;
}

fs.writeFileSync(new URL('./out/captions.srt', import.meta.url), `${output.join('\n')}\n`);
