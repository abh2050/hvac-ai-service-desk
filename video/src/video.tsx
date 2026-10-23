import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {fps, sceneFrames, scenes, startFrameFor} from './content';

const palette = {
  ink: '#101827',
  navy: '#17243b',
  paper: '#f4f1eb',
  green: '#0b8f73',
  mint: '#82d6c3',
  orange: '#f26a21',
  red: '#d83a3a',
  blue: '#79a7ff',
};

const sans = 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
const serif = 'Georgia, "Times New Roman", serif';

const Fade: React.FC<React.PropsWithChildren<{duration: number}>> = ({children, duration}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 14, duration - 12, duration], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return <AbsoluteFill style={{opacity}}>{children}</AbsoluteFill>;
};

const Kicker: React.FC<{children: React.ReactNode; tone?: 'green' | 'orange'}> = ({children, tone = 'green'}) => (
  <div
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      alignSelf: 'flex-start',
      borderRadius: 999,
      padding: '10px 18px',
      background: tone === 'green' ? 'rgba(11,143,115,.14)' : 'rgba(242,106,33,.14)',
      color: tone === 'green' ? palette.green : palette.orange,
      font: `700 20px/1 ${sans}`,
      letterSpacing: 1.6,
      textTransform: 'uppercase',
    }}
  >
    {children}
  </div>
);

const Caption: React.FC<{text: string; duration: number}> = ({text, duration}) => {
  const frame = useCurrentFrame();
  const words = text.split(/\s+/);
  const chunks: string[] = [];
  for (let i = 0; i < words.length; i += 9) chunks.push(words.slice(i, i + 9).join(' '));
  const index = Math.min(chunks.length - 1, Math.floor((frame / duration) * chunks.length));
  return (
    <div
      style={{
        position: 'absolute',
        left: 220,
        right: 220,
        bottom: 34,
        display: 'flex',
        justifyContent: 'center',
        zIndex: 30,
      }}
    >
      <div
        style={{
          maxWidth: 1320,
          borderRadius: 18,
          padding: '14px 24px 16px',
          color: 'white',
          background: 'rgba(10,18,31,.88)',
          boxShadow: '0 12px 36px rgba(0,0,0,.22)',
          font: `600 31px/1.25 ${sans}`,
          textAlign: 'center',
        }}
      >
        {chunks[index]}
      </div>
    </div>
  );
};

const SceneShell: React.FC<React.PropsWithChildren<{scene: number; dark?: boolean}>> = ({scene, dark = false, children}) => (
  <AbsoluteFill style={{background: dark ? palette.ink : palette.paper, color: dark ? 'white' : palette.ink, fontFamily: sans}}>
    {children}
    <Caption text={scenes[scene].narration} duration={sceneFrames[scene]} />
  </AbsoluteFill>
);

const Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps: sceneFps} = useVideoConfig();
  const rise = spring({fps: sceneFps, frame, config: {damping: 18, stiffness: 90}});
  const path = interpolate(frame, [8, 105], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <SceneShell scene={0} dark>
      <AbsoluteFill style={{background: 'radial-gradient(circle at 72% 32%, #223d59 0%, #101827 55%, #09101c 100%)'}} />
      <div style={{position: 'absolute', inset: '88px 110px 120px', display: 'grid', gridTemplateColumns: '1.05fr .95fr', gap: 92, alignItems: 'center'}}>
        <div style={{transform: `translateY(${(1 - rise) * 40}px)`, opacity: rise}}>
          <Kicker tone="orange">Uptime Desk</Kicker>
          <h1 style={{font: `700 94px/.98 ${serif}`, margin: '32px 0 28px', letterSpacing: -3}}>The alarm is the easy part.</h1>
          <p style={{font: `400 36px/1.35 ${sans}`, color: '#c7d2e3', maxWidth: 800}}>What failed? Which steps are safe? Who can reach it in time?</p>
        </div>
        <div style={{position: 'relative', height: 470, borderRadius: 34, border: '1px solid rgba(255,255,255,.16)', background: 'rgba(255,255,255,.06)', overflow: 'hidden'}}>
          <div style={{position: 'absolute', left: 38, top: 32, color: '#b7c4d8', font: `600 22px ${sans}`}}>SUPPLY AIR TEMPERATURE</div>
          <svg viewBox="0 0 700 360" style={{position: 'absolute', inset: '72px 28px 30px', width: 'calc(100% - 56px)', height: 'calc(100% - 102px)'}}>
            {[70, 150, 230, 310].map((y) => <line key={y} x1="0" x2="700" y1={y} y2={y} stroke="rgba(255,255,255,.10)" />)}
            <path d="M0 270 C80 260 105 245 160 250 S260 238 325 245 S400 220 460 225 S520 190 570 180 S640 85 700 66" fill="none" stroke={palette.mint} strokeWidth="8" strokeLinecap="round" strokeDasharray="900" strokeDashoffset={900 * (1 - path)} />
            <circle cx="700" cy="66" r="13" fill={palette.orange} opacity={path} />
          </svg>
          <div style={{position: 'absolute', right: 34, top: 94, borderRadius: 12, background: palette.orange, color: 'white', padding: '10px 14px', font: `700 20px ${sans}`, opacity: path}}>DRIFT DETECTED</div>
        </div>
      </div>
    </SceneShell>
  );
};

const Problem: React.FC = () => {
  const frame = useCurrentFrame();
  const cards = [
    ['01', 'Sensor alarm', 'Trend and timestamp'],
    ['02', 'Manual PDF', 'Safety and service steps'],
    ['03', 'Dispatch sheet', 'Skills, shifts, access'],
  ];
  return (
    <SceneShell scene={1}>
      <div style={{padding: '86px 110px 150px'}}>
        <Kicker>Before Uptime Desk</Kicker>
        <h2 style={{font: `700 72px/1.04 ${serif}`, margin: '28px 0 18px'}}>The evidence breaks at each handoff.</h2>
        <p style={{font: `400 28px/1.4 ${sans}`, color: '#566276', maxWidth: 1040}}>The manager has to reconstruct one decision from systems that do not share context.</p>
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 28, marginTop: 62}}>
          {cards.map(([n, title, sub], i) => {
            const p = spring({fps, frame: frame - i * 9, config: {damping: 18}});
            return (
              <div key={title} style={{opacity: p, transform: `translateY(${(1 - p) * 46}px)`, background: 'white', borderRadius: 26, padding: 36, boxShadow: '0 18px 55px rgba(25,37,55,.10)', borderTop: `7px solid ${i === 1 ? palette.orange : palette.green}`}}>
                <div style={{font: `700 20px ${sans}`, color: '#8a94a4'}}>{n}</div>
                <div style={{font: `700 39px/1.15 ${serif}`, marginTop: 34}}>{title}</div>
                <div style={{font: `400 24px/1.4 ${sans}`, color: '#667085', marginTop: 16}}>{sub}</div>
                <div style={{height: 2, background: '#e5e8ed', marginTop: 46}} />
                <div style={{font: `700 18px ${sans}`, color: palette.red, marginTop: 18}}>CONTEXT STOPS HERE</div>
              </div>
            );
          })}
        </div>
      </div>
    </SceneShell>
  );
};

const Architecture: React.FC = () => {
  const frame = useCurrentFrame();
  const duration = sceneFrames[2];
  const scale = interpolate(frame, [0, duration], [1.02, 1.13], {easing: Easing.inOut(Easing.ease), extrapolateRight: 'clamp'});
  const flows = ['Replay', 'Detect', 'Diagnose', 'Verify', 'Approve', 'Dispatch'];
  const active = Math.min(flows.length - 1, Math.floor((frame / duration) * flows.length));
  return (
    <SceneShell scene={2} dark>
      <AbsoluteFill style={{overflow: 'hidden'}}>
        <Img src={staticFile('aws-architecture.png')} style={{width: '100%', height: '100%', objectFit: 'contain', transform: `scale(${scale})`, filter: 'brightness(.55) saturate(.82)'}} />
        <AbsoluteFill style={{background: 'linear-gradient(90deg, rgba(10,18,31,.9), rgba(10,18,31,.18) 58%, rgba(10,18,31,.44))'}} />
      </AbsoluteFill>
      <div style={{position: 'absolute', left: 92, top: 72, width: 750}}>
        <Kicker tone="orange">AWS architecture</Kicker>
        <h2 style={{font: `700 68px/1.02 ${serif}`, margin: '26px 0 22px'}}>One path from sensor row to accountable work.</h2>
        <div style={{display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 34}}>
          {flows.map((flow, i) => (
            <div key={flow} style={{padding: '12px 18px', borderRadius: 999, font: `700 21px ${sans}`, background: i === active ? palette.orange : 'rgba(255,255,255,.11)', color: 'white', transform: `scale(${i === active ? 1.08 : 1})`}}>{flow}</div>
          ))}
        </div>
        <div style={{marginTop: 42, padding: '22px 26px', borderRadius: 20, background: 'rgba(11,143,115,.20)', border: '1px solid rgba(130,214,195,.35)', font: `600 24px/1.4 ${sans}`, color: '#d9fff6'}}>Code controls identity, citations, approval, and dispatch constraints.</div>
      </div>
    </SceneShell>
  );
};

type ClipSpec = {start: number; duration: number; file: string; sourceStart?: number; label: string; tone?: string};
const clips: ClipSpec[] = [
  {start: 0, duration: 12, file: 'live-flow.mp4', sourceStart: 0, label: 'REAL HOSTED RUN · LIVE PIPELINE'},
  {start: 12, duration: 11, file: 'rules.mp4', sourceStart: 0, label: 'OWNER RECORDING · RULES BESIDE MODEL'},
  {start: 23, duration: 11, file: 'evidence.mp4', sourceStart: 0, label: 'OWNER RECORDING · EVIDENCE PAGE'},
  {start: 34, duration: 11, file: 'live-flow.mp4', sourceStart: 35, label: 'REAL HOSTED RUN · APPROVAL TO DISPATCH'},
  {start: 45, duration: 7, file: 'assistant.mp4', sourceStart: 8, label: 'OWNER RECORDING · TECHNICIAN ASSISTANT'},
  {start: 52, duration: 6, file: 'blocked.mp4', sourceStart: 8, label: 'OWNER RECORDING · SAFE BLOCK'},
];

const DemoClip: React.FC<{clip: ClipSpec}> = ({clip}) => {
  const frame = useCurrentFrame();
  const duration = Math.ceil(clip.duration * fps);
  const zoom = interpolate(frame, [0, duration], [1.0, 1.055], {extrapolateRight: 'clamp'});
  return (
    <Fade duration={duration}>
      <AbsoluteFill style={{background: palette.ink}}>
        <OffthreadVideo
          src={staticFile(clip.file)}
          startFrom={Math.round((clip.sourceStart ?? 0) * fps)}
          muted
          style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${zoom})`}}
        />
        <AbsoluteFill style={{boxShadow: 'inset 0 0 160px rgba(4,10,19,.38)'}} />
        <div style={{position: 'absolute', left: 58, top: 50, padding: '12px 18px', borderRadius: 12, background: 'rgba(10,18,31,.90)', color: 'white', font: `700 19px ${sans}`, letterSpacing: 1.4}}>{clip.label}</div>
      </AbsoluteFill>
    </Fade>
  );
};

const Demo: React.FC = () => (
  <SceneShell scene={3} dark>
    {clips.map((clip) => (
      <Sequence key={`${clip.file}-${clip.start}`} from={Math.round(clip.start * fps)} durationInFrames={Math.round(clip.duration * fps)}>
        <DemoClip clip={clip} />
      </Sequence>
    ))}
    <div style={{position: 'absolute', right: 58, top: 50, padding: '11px 16px', borderRadius: 12, background: 'rgba(11,143,115,.92)', color: 'white', font: `700 18px ${sans}`}}>REPLAY OF RECORDED FIELD DATA</div>
  </SceneShell>
);

const Metric: React.FC<{eyebrow: string; value: string; comparison: string; note: string; delay?: number; accent?: string}> = ({eyebrow, value, comparison, note, delay = 0, accent = palette.green}) => {
  const frame = useCurrentFrame();
  const p = spring({fps, frame: frame - delay, config: {damping: 20}});
  return (
    <div style={{opacity: p, transform: `translateY(${(1 - p) * 38}px)`, background: 'white', borderRadius: 28, padding: '32px 34px', boxShadow: '0 18px 50px rgba(20,31,50,.10)', borderTop: `7px solid ${accent}`}}>
      <div style={{font: `700 17px ${sans}`, color: '#7b8493', letterSpacing: 1.3}}>{eyebrow}</div>
      <div style={{font: `700 64px/1 ${serif}`, marginTop: 24, color: accent}}>{value}</div>
      <div style={{font: `700 25px/1.25 ${sans}`, marginTop: 16}}>{comparison}</div>
      <div style={{font: `400 18px/1.35 ${sans}`, color: '#687385', marginTop: 18}}>{note}</div>
    </div>
  );
};

const Results: React.FC = () => {
  const frame = useCurrentFrame();
  const duration = sceneFrames[4];
  const phase = Math.min(2, Math.floor((frame / duration) * 3));
  return (
    <SceneShell scene={4}>
      <div style={{padding: '74px 105px 140px'}}>
        <div style={{display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between'}}>
          <div>
            <Kicker>Measured results</Kicker>
            <h2 style={{font: `700 63px/1.05 ${serif}`, margin: '24px 0 0'}}>The baseline wins stay on the page.</h2>
          </div>
          <div style={{font: `700 18px ${sans}`, color: '#687385', paddingBottom: 8}}>Sources: reports/gate-1.json, gate-2.json, gate-3.json</div>
        </div>
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 26, marginTop: 48}}>
          {phase === 0 && <>
            <Metric eyebrow="LAB AHU · RECALL" value="0.957" comparison="Model vs 0.739 rules" note="Measured against published LBNL ground truth." />
            <Metric eyebrow="LAB ECONOMIZER · RECALL" value="1.000" comparison="Rules beat 0.958 model" note="Rules remain the primary detector." delay={6} accent={palette.orange} />
            <Metric eyebrow="FIELD RTU · RECALL" value="0.648" comparison="Rules beat 0.187 model" note="Measured on two field units." delay={12} accent={palette.orange} />
          </>}
          {phase === 1 && <>
            <Metric eyebrow="DIAGNOSIS · CITATION SUPPORT" value="0.880" comparison="AI vs 0.122 keyword baseline" note="Run 3, 92 measured cases." />
            <Metric eyebrow="FIELD HOLDOUT · FAULT TYPE" value="0.750" comparison="Frozen pipeline" note="60 unused days from two field episodes." delay={6} accent={palette.blue} />
            <Metric eyebrow="HOSTED FLOW" value="8 / 10" comparison="2 runs blocked safely" note="No sourced lockout step meant no dispatch." delay={12} accent={palette.orange} />
          </>}
          {phase === 2 && <>
            <Metric eyebrow="DISPATCH SCENARIO · LATENESS" value="402 min" comparison="OR-Tools vs 1,343 nearest qualified" note="Scenario model result across 37 jobs." />
            <Metric eyebrow="EARLIEST AVAILABLE" value="402 min" comparison="Tied OR-Tools on lateness" note="The simple baseline stays visible." delay={6} accent={palette.blue} />
            <Metric eyebrow="CONSTRAINT VIOLATIONS" value="0" comparison="All methods" note="Computed dispatch result, not field savings." delay={12} accent={palette.green} />
          </>}
        </div>
      </div>
    </SceneShell>
  );
};

const Close: React.FC = () => {
  const frame = useCurrentFrame();
  const p = spring({fps, frame, config: {damping: 17}});
  return (
    <SceneShell scene={5} dark>
      <AbsoluteFill style={{background: 'radial-gradient(circle at 70% 10%, #214a52, #101827 58%, #081019)'}} />
      <div style={{position: 'absolute', inset: '90px 110px 135px', opacity: p, transform: `translateY(${(1 - p) * 32}px)`}}>
        <Kicker tone="orange">Uptime Desk</Kicker>
        <h2 style={{font: `700 82px/1 ${serif}`, margin: '28px 0 38px', maxWidth: 1160}}>Inspect the demo. Audit the evidence. Read the code.</h2>
        <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 34, maxWidth: 1440}}>
          <div style={{padding: 28, borderRadius: 20, background: 'rgba(255,255,255,.09)', font: `600 25px/1.5 ${sans}`}}>
            <div style={{color: palette.mint}}>RECORDED DEMO</div>
            <div>uptime-desk.vercel.app</div>
          </div>
          <div style={{padding: 28, borderRadius: 20, background: 'rgba(255,255,255,.09)', font: `600 25px/1.5 ${sans}`}}>
            <div style={{color: palette.mint}}>SOURCE AND EVIDENCE</div>
            <div>github.com/abh2050/hvac-ai-service-desk</div>
          </div>
        </div>
        <div style={{marginTop: 28, color: '#c2ccdb', font: `500 24px ${sans}`}}>abh2050.github.io/abhishek-shah-portfolio/</div>
      </div>
    </SceneShell>
  );
};

const sceneComponents = [Hook, Problem, Architecture, Demo, Results, Close];

export const Explainer: React.FC = () => (
  <AbsoluteFill style={{background: palette.ink}}>
    {scenes.map((scene, index) => {
      const Component = sceneComponents[index];
      return (
        <Sequence key={scene.id} from={startFrameFor(index)} durationInFrames={sceneFrames[index]}>
          <Component />
          <Audio src={staticFile(`scene-${scene.id}.mp3`)} />
        </Sequence>
      );
    })}
  </AbsoluteFill>
);
