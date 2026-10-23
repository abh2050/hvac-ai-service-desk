#!/usr/bin/env node

import {mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const credentials = process.env.HF_CREDENTIALS;
if (!credentials || !credentials.includes(':')) {
  throw new Error('HF_CREDENTIALS must contain the Higgsfield key ID and secret.');
}

const mode = process.argv[2] ?? 'hero';
const outputDirectory = path.resolve('docs/media/higgsfield');
const manifestPath = path.join(outputDirectory, 'manifest.json');
const authorization = {Authorization: `Key ${credentials}`};

const styleFrame = [
  'Visual identity: dark navy base, warm concrete neutral, and safety orange accent.',
  'Cool pre-dawn industrial lighting with restrained amber practical fixtures.',
  'A restrained 35 mm documentary lens, clean editorial realism, natural textures, and precise industrial detail.',
  'Cinematic but plausible. No logos, no readable brand names, no watermark, and no text overlay.',
].join(' ');

const persona = [
  'The same fictional facilities service manager appears in every frame:',
  'a South Asian man in his early forties with short black hair and a neatly trimmed beard,',
  'wearing a navy work jacket with subtle safety-orange piping, a charcoal shirt, work trousers,',
  'and a blank identification badge. He has a calm, observant expression.',
].join(' ');

const prompts = {
  hero: `${styleFrame} ${persona} A medium-wide view inside a modern commercial mechanical room before dawn. The manager stands beside a large air handler and studies a tablet with a simple trend graph. Blue morning light enters through a high window. Pipes, access panels, and service clearances are physically credible. Leave quiet negative space on the left for a website title.`,
  scene: `${styleFrame} ${persona} Show the same manager in the same mechanical room during the blue hour. He stands between the air handler and a small service cart while checking a tablet. The empty building feels quiet and time-sensitive. Frame the equipment, the person, and the practical work area clearly.`,
  before: `${styleFrame} ${persona} Show the same manager at a compact workstation beside the air handler. A sensor trend fills one monitor, an open service manual rests on the desk, and a printed dispatch sheet has handwritten marks. He compares the three sources with focused concern. Do not show readable text.`,
  resolved: `${styleFrame} ${persona} Show the same manager beside the same air handler after the decision is complete. His tablet shows a simple green verified status and a structured work-order layout with no readable text. He looks calm and ready to hand off the job. The equipment and lighting match the opening frame. Leave negative space on the right for closing copy.`,
};

const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

const requestJson = async (url, options = {}) => {
  const response = await fetch(url, {
    ...options,
    headers: {...authorization, ...(options.headers ?? {})},
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`Higgsfield request failed with ${response.status}: ${text.slice(0, 500)}`);
  }
  return text ? JSON.parse(text) : {};
};

const findImageUrl = (value) => {
  if (!value) return null;
  if (typeof value === 'string' && /^https?:\/\//.test(value)) return value;
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = findImageUrl(item);
      if (found) return found;
    }
  }
  if (typeof value === 'object') {
    for (const key of ['images', 'image', 'url', 'output', 'result', 'data']) {
      const found = findImageUrl(value[key]);
      if (found) return found;
    }
  }
  return null;
};

const submit = async (model, input) => {
  const submitted = await requestJson(`https://api.higgsfield.ai/${model}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(input),
  });
  let imageUrl = findImageUrl(submitted.images);
  if (imageUrl) return {imageUrl, requestId: submitted.request_id ?? submitted.id ?? null};

  const statusUrl = submitted.status_url;
  if (!statusUrl) throw new Error('Higgsfield did not return an image or status URL.');

  for (let attempt = 0; attempt < 120; attempt += 1) {
    await sleep(2500);
    const status = await requestJson(statusUrl);
    imageUrl = findImageUrl(status.images ?? status.output ?? status.result ?? status.data);
    if (imageUrl) return {imageUrl, requestId: submitted.request_id ?? submitted.id ?? null};
    const state = String(status.status ?? status.state ?? '').toLowerCase();
    if (['failed', 'error', 'cancelled', 'canceled'].includes(state)) {
      throw new Error(`Higgsfield generation ended with status ${state}.`);
    }
  }
  throw new Error('Higgsfield generation did not finish within five minutes.');
};

const download = async (url, name) => {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not download generated image: ${response.status}`);
  const contentType = response.headers.get('content-type') ?? '';
  const extension = contentType.includes('webp') ? 'webp' : contentType.includes('png') ? 'png' : 'jpg';
  const filePath = path.join(outputDirectory, `${name}.${extension}`);
  await writeFile(filePath, Buffer.from(await response.arrayBuffer()));
  return filePath;
};

await mkdir(outputDirectory, {recursive: true});
let manifest = {};
try {
  manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
} catch {
  manifest = {};
}

if (mode === 'hero') {
  const result = await submit('higgsfield-ai/soul/v2/standard', {
    prompt: prompts.hero,
    batch_size: 1,
    resolution: '1080p',
    aspect_ratio: '16:9',
    enhance_prompt: true,
    seed: 28417,
  });
  const filePath = await download(result.imageUrl, 'hero');
  manifest.hero = {url: result.imageUrl, file: path.relative(process.cwd(), filePath), requestId: result.requestId};
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`Saved hero image to ${manifest.hero.file}`);
} else if (mode === 'followups') {
  if (!manifest.hero?.url) throw new Error('Generate and approve the hero image first.');
  for (const name of ['scene', 'before', 'resolved']) {
    const result = await submit('higgsfield-ai/soul/v2/image-to-image', {
      image_url: manifest.hero.url,
      prompt: prompts[name],
      batch_size: 1,
      resolution: '1080p',
      aspect_ratio: '16:9',
      enhance_prompt: true,
      seed: {scene: 28429, before: 28439, resolved: 28447}[name],
    });
    const filePath = await download(result.imageUrl, name);
    manifest[name] = {url: result.imageUrl, file: path.relative(process.cwd(), filePath), requestId: result.requestId};
    await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
    console.log(`Saved ${name} image to ${manifest[name].file}`);
  }
} else {
  throw new Error('Use either hero or followups.');
}
