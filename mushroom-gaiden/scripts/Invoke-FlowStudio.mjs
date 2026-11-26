#!/usr/bin/env node
/**
 * Invoke-FlowStudio.mjs
 *
 * Direct CDP + Playwright automation runner for Mushroom Gaiden on Google Flow (flow.google.com).
 * Uses CDP port 9333 and the updated 11/23/2026 modules in C:\Users\chase\mcp\google-flow-mcp\src\.
 *
 * Subcommands:
 *   create-project  --name "Mushroom Gaiden - Toad & Toadette Shinobi"
 *   gen-image       --prompt "..." --out-prefix "ref_toad_hayabusa" [--refs "a.webp,b.webp"] [--model "Nano Banana 2"] [--ratio "16:9"]
 *   gen-shot-images --shots "shot_01,shot_02,shot_03" [--manifest "..\shots.json"] [--skip-existing]
 *   gen-video       --shots "shot_01" | --all [--manifest "..\shots.json"] [--skip-existing]
 */

import fs from 'fs';
import path from 'path';
import { execFileSync } from 'child_process';
import { fileURLToPath, pathToFileURL } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_DIR = path.resolve(__dirname, '..');
const FLOW_PROJECT_FILE = path.join(PROJECT_DIR, 'flow_project.json');
const FRAMES_DIR = path.join(PROJECT_DIR, 'frames');
const VIDEOS_DIR = path.join(PROJECT_DIR, 'videos');
const CDP_URL = 'http://127.0.0.1:9333';

const MCP_ROOT = 'C:\\Users\\chase\\mcp\\google-flow-mcp';
const { chromium } = await import(pathToFileURL(path.join(MCP_ROOT, 'node_modules', 'playwright', 'index.mjs')).href);
const { connectToBrowser, setPage } = await import(pathToFileURL(path.join(MCP_ROOT, 'src', 'browser', 'connect.js')).href);
const { handleGenerateImage } = await import(pathToFileURL(path.join(MCP_ROOT, 'src', 'tools', 'generate-image.js')).href);

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const k = a.slice(2);
      const next = argv[i + 1];
      if (!next || next.startsWith('--')) {
        args[k] = true;
      } else {
        args[k] = next;
        i++;
      }
    } else {
      args._.push(a);
    }
  }
  return args;
}

async function getFlowPage() {
  const browser = await chromium.connectOverCDP(CDP_URL);
  const ctx = browser.contexts()[0] || await browser.newContext();
  const pages = ctx.pages();
  const page =
    pages.find((p) => p.url().includes('flow.google.com')) ||
    pages.find((p) => p.url().includes('labs.google')) ||
    pages.find((p) => !p.url().startsWith('chrome-extension')) ||
    pages[0] ||
    (await ctx.newPage());
  return { browser, ctx, page };
}

function loadProjectJson() {
  if (!fs.existsSync(FLOW_PROJECT_FILE)) {
    throw new Error(`Missing ${FLOW_PROJECT_FILE}. Run create-project first.`);
  }
  return JSON.parse(fs.readFileSync(FLOW_PROJECT_FILE, 'utf-8'));
}

async function dismissOpenPicker(page) {
  const searchBox = page.locator('input[placeholder="Search assets"]').first();
  if (await searchBox.isVisible().catch(() => false)) {
    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(400);
  }
  // If still visible, click the close button in the composer
  if (await searchBox.isVisible().catch(() => false)) {
    await page.mouse.click(200, 200).catch(() => {});
    await page.waitForTimeout(300);
  }
}

async function clearAttachedChips(page) {
  await dismissOpenPicker(page);
  // Click any remove/close buttons on attached ingredient chips inside the composer area (x > 950, y > 680)
  for (let pass = 0; pass < 6; pass++) {
    const removed = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      for (const b of btns) {
        const rect = b.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;
        // Composer chips sit above the prompt input on the right panel (x > 950, y > 620)
        if (rect.x < 950 || rect.y < 620) continue;
        const aria = (b.getAttribute('aria-label') || '').toLowerCase();
        const txt = (b.innerText || '').trim().toLowerCase();
        // Skip main buttons like add, arrow_forward, Settings trigger, close picker
        if (aria.includes('ingredients') || aria.includes('start generation') || aria.includes('settings')) continue;
        if (aria.includes('remove') || aria.includes('delete') || aria.includes('clear') || (txt === 'close' && rect.width <= 32)) {
          b.click();
          return true;
        }
      }
      return false;
    });
    if (!removed) break;
    await page.waitForTimeout(300);
  }
}

async function openIngredientPicker(page) {
  const searchBox = page.locator('input[placeholder="Search assets"]').first();
  if (await searchBox.isVisible().catch(() => false)) return searchBox;

  const trigger = page
    .locator('button[aria-label="Add ingredients to the prompt box"], button:has(:text-is("add_2"))')
    .last();
  await trigger.waitFor({ state: 'visible', timeout: 10000 });
  await trigger.click();
  await searchBox.waitFor({ state: 'visible', timeout: 8000 });
  await page.waitForTimeout(400);
  return searchBox;
}

async function attachIngredients(page, absPaths, debugName = null) {
  await clearAttachedChips(page);
  const attached = [];

  for (const filePath of absPaths) {
    if (!fs.existsSync(filePath)) {
      throw new Error(`Reference asset not found: ${filePath}`);
    }
    const baseName = path.basename(filePath);
    const stemName = path.basename(filePath, path.extname(filePath));

    let searchBox = await openIngredientPicker(page);

    // Click Uploads tab inside picker if present
    const uploadsTab = page.locator('button:has-text("Uploads"), [role="tab"]:has-text("Uploads"), div:has-text("Uploads")').filter({ hasText: /^Uploads$/ }).last();
    if (await uploadsTab.isVisible({ timeout: 1500 }).catch(() => false)) {
      await uploadsTab.click().catch(() => {});
      await page.waitForTimeout(600);
    }

    await searchBox.fill(stemName);
    await page.waitForTimeout(800);

    // Check if matching item exists in Uploads
    let matchRow = page.locator('button, [role="option"], [role="listitem"], div').filter({ hasText: stemName }).last();
    let foundExisting = await matchRow.isVisible({ timeout: 1200 }).catch(() => false);
    // Avoid matching the search input itself or whole container
    if (foundExisting) {
      const box = await matchRow.boundingBox().catch(() => null);
      if (!box || box.height > 120 || box.width > 450) {
        foundExisting = false;
      }
    }

    if (!foundExisting) {
      // Upload via Upload media button + filechooser
      const uploadBtn = page.locator('button:has-text("Upload media"), div[role="button"]:has-text("Upload media")').last();
      await uploadBtn.waitFor({ state: 'visible', timeout: 5000 });
      const [chooser] = await Promise.all([
        page.waitForEvent('filechooser', { timeout: 10000 }),
        uploadBtn.click(),
      ]);
      await chooser.setFiles([filePath]);
      await page.waitForTimeout(4000);

      // Dismiss any first-time upload consent modal if shown
      const consentBtn = page.locator('button:has-text("I agree"), button:has-text("Accept"), button:has-text("Agree")').first();
      if (await consentBtn.isVisible({ timeout: 1500 }).catch(() => false)) {
        await consentBtn.click();
        await page.waitForTimeout(1200);
      }

      // Ensure picker is open and search Uploads for uploaded file
      searchBox = await openIngredientPicker(page);
      const uTab = page.locator('button:has-text("Uploads"), div:has-text("Uploads")').filter({ hasText: /^Uploads$/ }).last();
      if (await uTab.isVisible({ timeout: 1500 }).catch(() => false)) {
        await uTab.click().catch(() => {});
        await page.waitForTimeout(800);
      }
      await searchBox.fill(stemName);
      await page.waitForTimeout(1200);
    }

    // Select the first visible asset row in the picker's asset list
    const rowClicked = await page.evaluate((targetStem) => {
      const searchInp = document.querySelector('input[placeholder="Search assets"]');
      if (!searchInp) return false;
      const dialogRoot = searchInp.closest('[role="dialog"], .cdk-overlay-pane, div[class*="menu"], div[class*="popover"]') || searchInp.parentElement?.parentElement?.parentElement;
      if (!dialogRoot) return false;
      const candidates = Array.from(dialogRoot.querySelectorAll('button, [role="option"], [role="listitem"], div'));
      for (const el of candidates) {
        const rect = el.getBoundingClientRect();
        if (rect.width < 100 || rect.width > 420 || rect.height < 36 || rect.height > 100) continue;
        const txt = (el.innerText || '').trim();
        if (txt.includes(targetStem) || txt.includes('Image')) {
          el.click();
          return txt.slice(0, 80);
        }
      }
      return false;
    }, stemName);

    if (!rowClicked) {
      await page.screenshot({ path: path.join(__dirname, `debug_attach_miss_${stemName}.png`) });
      throw new Error(`Could not locate uploaded asset "${baseName}" inside Flow picker.`);
    }

    await page.waitForTimeout(600);
    const addToPromptBtn = page.locator('button:has-text("Add to prompt"), button:has-text("Add to Prompt")').last();
    await addToPromptBtn.waitFor({ state: 'visible', timeout: 5000 });
    await addToPromptBtn.click();
    await page.waitForTimeout(800);

    attached.push(baseName);
    await dismissOpenPicker(page);
  }

  if (debugName) {
    await page.screenshot({ path: path.join(__dirname, debugName) });
  }
  return attached;
}

async function cmdCreateProject(args) {
  const name = args.name || 'Mushroom Gaiden - Toad & Toadette Shinobi';
  const { page } = await getFlowPage();

  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(300);

  await page.goto('https://flow.google.com/', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(1500);

  const backdrop = page.locator('.cdk-overlay-backdrop-showing').first();
  if (await backdrop.isVisible().catch(() => false)) {
    await backdrop.click({ position: { x: 10, y: 10 }, force: true }).catch(() => {});
    await page.waitForTimeout(400);
  }

  const newBtn = page.locator('button:has-text("New project")').first();
  await newBtn.waitFor({ state: 'visible', timeout: 15000 });
  await newBtn.click();

  await page.waitForURL(/\/project\/[a-f0-9-]+/i, { timeout: 20000 });
  await page.waitForTimeout(2500);

  const projectUrl = page.url();
  const match = projectUrl.match(/\/project\/([a-f0-9-]+)/i);
  const projectId = match ? match[1] : null;

  const payload = {
    name,
    projectId,
    url: projectUrl,
    renamed: false,
    created_at: new Date().toISOString(),
  };
  fs.writeFileSync(FLOW_PROJECT_FILE, JSON.stringify(payload, null, 2));
  console.log(JSON.stringify({ ok: true, project: payload }, null, 2));
}

async function generateOneImage(prompt, outPrefix, refPaths, model = 'Nano Banana 2', ratio = '16:9', debugShot = null) {
  const proj = loadProjectJson();
  fs.mkdirSync(FRAMES_DIR, { recursive: true });

  const { page } = await connectToBrowser({ cdpPort: 9333 });
  setPage(page);

  if (!page.url().includes(proj.projectId)) {
    await page.goto(proj.url, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2500);
  }
  await dismissOpenPicker(page);

  let attachedRefs = [];
  if (refPaths && refPaths.length > 0) {
    attachedRefs = await attachIngredients(page, refPaths, debugShot);
  }

  const result = await handleGenerateImage({
    prompt,
    model,
    ratio,
    reference_images: [],
    auto_confirm: true,
    output_folder: FRAMES_DIR,
    response_format: 'detailed',
  });

  const savedVariants = [];
  const artifacts = result.artifacts || [];
  for (let i = 0; i < artifacts.length; i++) {
    const src = artifacts[i].path;
    const ext = path.extname(src) || '.webp';
    const dest = path.join(FRAMES_DIR, `${outPrefix}_v${i + 1}${ext}`);
    fs.copyFileSync(src, dest);
    savedVariants.push(dest);
  }

  return {
    out_prefix: outPrefix,
    attached_refs: attachedRefs,
    variants: savedVariants,
    ai_response_message: result.ai_response_message,
  };
}

async function cmdGenImage(args) {
  if (!args.prompt) throw new Error('--prompt is required');
  if (!args['out-prefix']) throw new Error('--out-prefix is required');
  const refs = args.refs
    ? String(args.refs)
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
        .map((p) => (path.isAbsolute(p) ? p : path.resolve(PROJECT_DIR, p)))
    : [];
  const res = await generateOneImage(
    args.prompt,
    args['out-prefix'],
    refs,
    args.model || 'Nano Banana 2',
    args.ratio || '16:9',
    args['debug-pre'] || null
  );
  console.log(JSON.stringify({ ok: true, ...res }, null, 2));
}

async function cmdGenShotImages(args) {
  const manifestPath = args.manifest
    ? path.resolve(PROJECT_DIR, args.manifest)
    : path.join(PROJECT_DIR, 'shots.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));

  let targetShots = manifest.shots || [];
  if (!args.all) {
    if (!args.shots) throw new Error('Pass --shots shot_01,shot_02 or --all');
    const wanted = new Set(String(args.shots).split(',').map((s) => s.trim()).filter(Boolean));
    targetShots = targetShots.filter((s) => wanted.has(s.id));
  }
  if (!targetShots.length) throw new Error('No matching shots found');

  const out = [];
  for (const shot of targetShots) {
    const v1Check = path.join(FRAMES_DIR, `${shot.id}_v1.webp`);
    if (args['skip-existing'] && fs.existsSync(v1Check)) {
      out.push({ id: shot.id, skipped: true });
      continue;
    }
    const refs = (shot.refs || []).map((r) => (path.isAbsolute(r) ? r : path.resolve(PROJECT_DIR, r)));
    const debugName = shot.id === 'shot_01' ? 'debug_shot_01_img_pre.png' : null;
    console.error(`[${shot.id}] Generating keyframe with refs: ${refs.map((x) => path.basename(x)).join(', ')}`);
    const res = await generateOneImage(shot.image_prompt, shot.id, refs, 'Nano Banana 2', '16:9', debugName);
    out.push({ id: shot.id, ...res });
  }
  console.log(JSON.stringify({ ok: true, shots: out }, null, 2));
}

function validateMp4(mp4Path) {
  if (!fs.existsSync(mp4Path)) throw new Error(`MP4 missing: ${mp4Path}`);
  const size = fs.statSync(mp4Path).size;
  if (size < 300 * 1024) {
    throw new Error(`MP4 too small (${size} bytes): ${mp4Path}`);
  }
  const out = execFileSync(
    'ffprobe',
    ['-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', mp4Path],
    { encoding: 'utf-8' }
  );
  const info = JSON.parse(out);
  const v = (info.streams || []).find((s) => s.codec_type === 'video');
  const a = (info.streams || []).find((s) => s.codec_type === 'audio');
  const duration = parseFloat(info.format?.duration || '0');
  if (!v || v.codec_name !== 'h264' || duration < 4.0) {
    throw new Error(`Invalid ffprobe stream on ${mp4Path}: codec=${v?.codec_name}, duration=${duration}`);
  }
  return {
    bytes: size,
    duration_sec: duration,
    width: v.width,
    height: v.height,
    fps: v.r_frame_rate,
    has_audio: Boolean(a),
    sample_rate: a ? Number(a.sample_rate) : 0,
  };
}

async function cmdGenVideo(args) {
  const manifestPath = args.manifest
    ? path.resolve(PROJECT_DIR, args.manifest)
    : path.join(PROJECT_DIR, 'shots.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
  const proj = loadProjectJson();
  fs.mkdirSync(VIDEOS_DIR, { recursive: true });

  let targetShots = manifest.shots || [];
  if (!args.all) {
    if (!args.shots) throw new Error('Pass --shots shot_01,shot_02 or --all');
    const wanted = new Set(String(args.shots).split(',').map((s) => s.trim()).filter(Boolean));
    targetShots = targetShots.filter((s) => wanted.has(s.id));
  }
  if (!targetShots.length) throw new Error('No matching shots found');

  const { page } = await getFlowPage();
  const ensureProjectView = async () => {
    const inEditor = await page.locator('button:has-text("Done"), [placeholder*="Describe how to edit this video"]').first().isVisible().catch(() => false);
    if (!page.url().includes(proj.projectId) || inEditor) {
      await page.goto(proj.url, { waitUntil: 'networkidle', timeout: 30000 });
      await page.waitForTimeout(2500);
    }
    await dismissOpenPicker(page);
  };
  await ensureProjectView();

  const results = [];
  for (const shot of targetShots) {
    const outPath = path.join(VIDEOS_DIR, `${shot.id}.mp4`);
    if (args['skip-existing'] && fs.existsSync(outPath)) {
      const probe = validateMp4(outPath);
      results.push({ id: shot.id, skipped: true, path: outPath, probe });
      continue;
    }

    await ensureProjectView();
    const keyframePath = path.resolve(PROJECT_DIR, shot.keyframe || path.join('frames', `${shot.id}_canon.webp`));
    console.error(`[${shot.id}] Attaching keyframe: ${keyframePath}`);

    const baseline = await page.evaluate(() => {
      const videoKey = (s) => {
        const m = (s || '').match(/\/asb\/([^=?]+)/);
        return m ? m[1].slice(0, 50) : s;
      };
      const videoKeys = new Set();
      document.querySelectorAll('video, video source').forEach((el) => {
        const s = el.currentSrc || el.src || el.getAttribute('src') || '';
        if (s) videoKeys.add(videoKey(s));
      });
      const asbImgs = new Set();
      document.querySelectorAll('img').forEach((img) => {
        const m = (img.src || '').match(/flow\.google\.com\/asb\/([^=?]+)/);
        if (m) asbImgs.add(m[1].slice(0, 50));
      });
      const bodyTxt = document.body.innerText || '';
      const startedCount = (bodyTxt.match(/generation has started/gi) || []).length;
      return { videoKeys: [...videoKeys], asbImgs: [...asbImgs], startedCount };
    });
    const baselineApproveCount = await page.getByText('Approve', { exact: true }).count().catch(() => 0);

    await attachIngredients(page, [keyframePath], null);

    const promptInput = page.locator('[contenteditable="true"]:visible, textarea:visible').last();
    await promptInput.waitFor({ state: 'visible', timeout: 10000 });

    const jpCue = shot.dialogue_jp ? ` Spoken Japanese dialogue with lip-sync: ${shot.dialogue_jp}` : '';
    const videoPrompt =
      `Generate 1 6-second 16:9 video using Omni 1.2 Flash based on the attached reference image immediately without asking questions. ` +
      `Strictly follow this camera motion, choreography, and audio cue: ${shot.video_prompt}${jpCue}`;

    await dismissOpenPicker(page);
    await promptInput.click();
    await page.keyboard.press('Control+A');
    await page.keyboard.press('Backspace');
    await page.waitForTimeout(200);
    await promptInput.type(videoPrompt, { delay: 3, timeout: 60000 });
    await page.waitForTimeout(600);

    const debugPrePath = path.join(__dirname, `debug_${shot.id}_pre.png`);
    await page.screenshot({ path: debugPrePath, fullPage: false });
    console.error(`[${shot.id}] Saved pre-submit screenshot: ${debugPrePath}`);

    const submitBtn = page.locator('button:has(:text-is("arrow_forward")), button[aria-label="Start generation"]').last();
    await submitBtn.waitFor({ state: 'visible', timeout: 10000 });
    await submitBtn.click();

    const startMs = Date.now();
    const timeoutMs = 360000;
    let approved = false;
    let newVideoSrc = null;

    while (Date.now() - startMs < timeoutMs) {
      await page.waitForTimeout(3000);

      // Keep right-hand Agent sidebar scrolled to bottom so latest confirmation & cards are visible
      await page.evaluate(() => {
        document.querySelectorAll('div, section, main').forEach((el) => {
          const r = el.getBoundingClientRect();
          if (r.x > 950 && el.scrollHeight > el.clientHeight + 20) {
            el.scrollTop = el.scrollHeight;
          }
        });
      }).catch(() => {});

      // 1. Auto-approve ONLY the newest English credit confirmation dialog (.last())
      if (!approved) {
        const currApproveCount = await page.getByText('Approve', { exact: true }).count().catch(() => 0);
        if (currApproveCount > baselineApproveCount) {
          const newestApprove = page.getByText('Approve', { exact: true }).last();
          await newestApprove.scrollIntoViewIfNeeded().catch(() => {});
          await page.waitForTimeout(250);
          await newestApprove.click({ force: true }).catch(() => {});
          await page.waitForTimeout(1500);
          const startedNow = await page.evaluate(
            () => ((document.body.innerText || '').match(/generation has started/gi) || []).length
          ).catch(() => 0);
          if (startedNow > baseline.startedCount) {
            approved = true;
            console.error(`[${shot.id}] Confirmed Approve (startedNow=${startedNow})`);
          } else {
            console.error(`[${shot.id}] Clicked newest Approve (${currApproveCount} > ${baselineApproveCount}), verifying start...`);
          }
        } else {
          const startedNow = await page.evaluate(
            () => ((document.body.innerText || '').match(/generation has started/gi) || []).length
          ).catch(() => 0);
          if (startedNow > baseline.startedCount) {
            approved = true;
            console.error(`[${shot.id}] Generation started cleanly (startedNow=${startedNow})`);
          }
        }
      }

      // 2. Check for policy refusal or cancelled confirmation in ONLY the latest chat turn
      const failReason = await page.evaluate(() => {
        const full = document.body.innerText || '';
        const marker = 'Generate 1 6-second 16:9 video';
        const idx = full.lastIndexOf(marker);
        const tail = idx >= 0 ? full.slice(idx) : full.slice(-1200);
        if (/timed out waiting for confirmation|was cancelled/i.test(tail)) {
          return `CANCELLED: ${tail.slice(-300)}`;
        }
        if (/violates? our (policy|policies|guidelines)|unable to generate|cannot generate|against our safety|blocked by safety/i.test(tail)) {
          return `POLICY_REFUSAL: ${tail.slice(-300)}`;
        }
        return null;
      });
      if (failReason) {
        await page.screenshot({ path: path.join(__dirname, `debug_${shot.id}_failed.png`) });
        throw new Error(`[${shot.id}] ${failReason}`);
      }

      // 3. Scan DOM for the NEW video tile matching THIS shot's prompt in img.alt (prevents ever grabbing an earlier shot)
      if (approved && Date.now() - startMs > 18000) {
        const promptSnippet = shot.video_prompt.slice(0, 48);
        const candidateThumbs = await page.evaluate(
          ({ baseAsb, snippet }) => {
            const out = [];
            document.querySelectorAll('img').forEach((img) => {
              const src = img.src || '';
              const m = src.match(/flow\.google\.com\/asb\/([^=?]+)/);
              if (!m) return;
              const tok = m[1];
              if (baseAsb.includes(tok.slice(0, 50))) return;
              const alt = img.alt || '';
              // Strictly match ONLY the grid tile whose img.alt contains THIS shot's prompt snippet
              if (alt.includes(snippet)) {
                out.push(`https://flow.google.com/asb/${tok}=mm,22,15`);
              }
            });
            return [...new Set(out)];
          },
          { baseAsb: baseline.asbImgs, snippet: promptSnippet }
        );

        for (const cand of candidateThumbs) {
          try {
            const headResp = await page.context().request.get(cand, { timeout: 15000 });
            const ct = headResp.headers()['content-type'] || '';
            if (headResp.ok() && ct.startsWith('video/')) {
              newVideoSrc = cand;
              console.error(`[${shot.id}] Verified & detected rendered video: ${cand.slice(0, 90)}`);
              break;
            }
          } catch {
            // Not yet ready or non-video asset
          }
        }
        if (newVideoSrc) break;
      }
    }

    if (!newVideoSrc) {
      const timeoutPng = path.join(__dirname, `debug_${shot.id}_timeout.png`);
      await page.screenshot({ path: timeoutPng });
      throw new Error(`[${shot.id}] Timed out waiting for generated video (screenshot: ${timeoutPng})`);
    }

    // Download using Playwright context request (shares cookies, bypasses CORS redirects on /asb/ video streams)
    let buf = null;
    let dlStatus = 0;
    try {
      const resp = await page.context().request.get(newVideoSrc, { timeout: 90000 });
      dlStatus = resp.status();
      if (resp.ok()) {
        buf = await resp.body();
      }
    } catch (e) {
      console.error(`[${shot.id}] page.context().request.get failed: ${e.message}`);
    }

    // Fallback: in-page fetch with credentials/no-cors check or flow download button if needed
    if (!buf || buf.length < 100000) {
      const dl = await page.evaluate(async (url) => {
        const resp = await fetch(url, { credentials: 'include' });
        if (!resp.ok) return { ok: false, status: resp.status };
        const blob = await resp.blob();
        const b64 = await new Promise((resolve) => {
          const r = new FileReader();
          r.onloadend = () => resolve(String(r.result).split(',')[1]);
          r.readAsDataURL(blob);
        });
        return { ok: true, type: blob.type, b64 };
      }, newVideoSrc).catch((e) => ({ ok: false, status: e.message }));
      if (dl.ok && dl.b64) {
        buf = Buffer.from(dl.b64, 'base64');
      } else {
        dlStatus = dl.status || dlStatus;
      }
    }

    // Close modal player if opened
    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(400);

    if (!buf || buf.length < 100000) {
      throw new Error(`[${shot.id}] Failed to download video from ${newVideoSrc} (status=${dlStatus}, bytes=${buf?.length || 0})`);
    }

    fs.writeFileSync(outPath, buf);
    const probe = validateMp4(outPath);
    console.error(`[${shot.id}] Saved & validated ${outPath} (${probe.duration_sec}s, ${probe.width}x${probe.height}, ${probe.bytes} bytes)`);
    results.push({ id: shot.id, skipped: false, path: outPath, probe });
  }

  console.log(JSON.stringify({ ok: true, results }, null, 2));
}

const [cmd, ...rest] = process.argv.slice(2);
const args = parseArgs(rest);

try {
  if (cmd === 'create-project') {
    await cmdCreateProject(args);
  } else if (cmd === 'gen-image') {
    await cmdGenImage(args);
  } else if (cmd === 'gen-shot-images') {
    await cmdGenShotImages(args);
  } else if (cmd === 'gen-video') {
    await cmdGenVideo(args);
  } else {
    console.error('Unknown subcommand. Use create-project, gen-image, gen-shot-images, or gen-video.');
    process.exit(2);
  }
  process.exit(0);
} catch (err) {
  console.error('ERROR:', err.stack || err.message || err);
  process.exit(1);
}
