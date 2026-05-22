import fs from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");
const engineRoot = path.join(repoRoot, "services", "python-engine");
const bundledSampleWorkspace = path.join(engineRoot, "app", "bundled_sample_workspace");
const smokeRoot = path.join(os.tmpdir(), `textflow-real-smoke-${Date.now()}`);
const screenshotsDir = path.join(smokeRoot, "screenshots");
const viewport = { width: Number(process.env.TEXTFLOW_SMOKE_WIDTH ?? 1280), height: Number(process.env.TEXTFLOW_SMOKE_HEIGHT ?? 720) };
const workflowTimeoutMs = Number(process.env.TEXTFLOW_SMOKE_WORKFLOW_TIMEOUT_MS ?? 480000);

const childProcesses = [];

async function npmInvocation() {
  if (process.platform !== "win32") {
    return { command: "npm", argsPrefix: [] };
  }
  const npmCli = path.join(path.dirname(process.execPath), "node_modules", "npm", "bin", "npm-cli.js");
  await fs.access(npmCli).catch(() => {
    throw new Error(`npm CLI script is missing: ${npmCli}`);
  });
  return { command: process.execPath, argsPrefix: [npmCli] };
}

function pythonCommand() {
  const windowsVenv = path.join(engineRoot, ".venv", "Scripts", "python.exe");
  const posixVenv = path.join(engineRoot, ".venv", "bin", "python");
  if (process.platform === "win32") {
    return windowsVenv;
  }
  return posixVenv;
}

function chromeCandidates() {
  if (process.env.TEXTFLOW_SMOKE_CHROME) {
    return [process.env.TEXTFLOW_SMOKE_CHROME];
  }
  if (process.platform === "win32") {
    return [
      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
      "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
    ];
  }
  if (process.platform === "darwin") {
    return [
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
      "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
      "google-chrome",
      "chromium"
    ];
  }
  return ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"];
}

async function firstExisting(candidates) {
  for (const candidate of candidates) {
    if (!candidate.includes(path.sep) && !candidate.includes("/")) {
      return candidate;
    }
    try {
      await fs.access(candidate);
      return candidate;
    } catch {
      // Try the next common browser path.
    }
  }
  throw new Error(`No Chrome-compatible browser found. Set TEXTFLOW_SMOKE_CHROME to override.`);
}

async function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => {
        if (!address || typeof address === "string") {
          reject(new Error("Could not reserve a local port."));
          return;
        }
        resolve(address.port);
      });
    });
  });
}

function spawnLogged(command, args, options) {
  const child = spawn(command, args, {
    ...options,
    stdio: ["ignore", "pipe", "pipe"]
  });
  const logs = [];
  const record = { child, label: options?.label ?? command, logs };
  childProcesses.push(record);
  const capture = (stream, prefix) => {
    stream.setEncoding("utf8");
    stream.on("data", (chunk) => {
      logs.push(`${prefix}${chunk}`);
      if (logs.length > 80) {
        logs.splice(0, logs.length - 80);
      }
    });
  };
  capture(child.stdout, "");
  capture(child.stderr, "ERR ");
  child.once("exit", (code, signal) => {
    if (code !== 0 && signal !== "SIGTERM") {
      logs.push(`EXIT code=${code} signal=${signal ?? ""}`);
    }
  });
  return record;
}

function stopChild(child) {
  if (!child.pid || child.exitCode !== null || child.signalCode !== null) {
    return;
  }
  if (process.platform === "win32") {
    const result = spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    if (result.status === 0) {
      return;
    }
  }
  child.kill();
}

function stopAllChildren() {
  for (const record of childProcesses.reverse()) {
    try {
      stopChild(record.child);
    } catch {
      // Best-effort cleanup.
    }
  }
}

function processLogSummary() {
  return childProcesses.map((record) => ({
    label: record.label,
    logs: record.logs.slice(-30)
  }));
}

async function waitForHttp(url, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs;
  let lastError = "";
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
      lastError = `${response.status} ${response.statusText}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await sleep(250);
  }
  throw new Error(`${label} did not become ready at ${url}: ${lastError}`);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

class CdpClient {
  constructor(wsUrl) {
    if (typeof WebSocket === "undefined") {
      throw new Error("This script needs Node.js with global WebSocket support.");
    }
    this.wsUrl = wsUrl;
    this.ws = new WebSocket(wsUrl);
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = new Map();
  }

  async connect() {
    await new Promise((resolve, reject) => {
      this.ws.addEventListener("open", resolve, { once: true });
      this.ws.addEventListener("error", reject, { once: true });
    });
    this.ws.addEventListener("message", (event) => {
      const message = JSON.parse(String(event.data));
      if (message.id && this.pending.has(message.id)) {
        const { resolve, reject } = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) {
          reject(new Error(`${message.error.message}: ${message.error.data ?? ""}`));
        } else {
          resolve(message.result);
        }
        return;
      }
      if (message.method && this.listeners.has(message.method)) {
        for (const listener of this.listeners.get(message.method)) {
          listener(message.params ?? {});
        }
      }
    });
  }

  on(method, listener) {
    const listeners = this.listeners.get(method) ?? [];
    listeners.push(listener);
    this.listeners.set(method, listeners);
  }

  send(method, params = {}, timeoutMs = 15000) {
    const id = this.nextId++;
    const payload = JSON.stringify({ id, method, params });
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP command timed out: ${method}`));
      }, timeoutMs);
      this.pending.set(id, {
        resolve: (value) => {
          clearTimeout(timer);
          resolve(value);
        },
        reject: (error) => {
          clearTimeout(timer);
          reject(error);
        }
      });
      this.ws.send(payload);
    });
  }

  close() {
    this.ws.close();
  }
}

async function evaluate(cdp, expression, timeoutMs = 5000) {
  const result = await cdp.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
    timeout: timeoutMs
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text ?? "Runtime.evaluate failed");
  }
  return result.result?.value;
}

async function waitForPredicate(cdp, expression, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await evaluate(cdp, expression).catch(() => false)) {
      return;
    }
    await sleep(350);
  }
  const visibleText = await evaluate(cdp, `document.body?.innerText?.slice(0, 1400) ?? ""`, 1000).catch(() => "");
  throw new Error(`Timed out waiting for ${label}.\nVisible text:\n${visibleText}`);
}

async function clickButton(cdp, label) {
  const target = await evaluate(cdp, `
    (() => {
      const wanted = ${JSON.stringify(label)};
      const elements = Array.from(document.querySelectorAll('button,[role="button"]'));
      for (const element of elements) {
        const text = (element.innerText || element.textContent || element.getAttribute('aria-label') || '').trim();
        const aria = (element.getAttribute('aria-label') || '').trim();
        const title = (element.getAttribute('title') || '').trim();
        const disabled = element.disabled || element.getAttribute('aria-disabled') === 'true';
        const rect = element.getBoundingClientRect();
        if (!disabled && rect.width > 0 && rect.height > 0 && (text === wanted || aria === wanted || title === wanted)) {
          return {
            x: Math.round(rect.left + rect.width / 2),
            y: Math.round(rect.top + rect.height / 2),
            text,
            aria,
            title
          };
        }
      }
      return null;
    })()
  `);
  if (!target) {
    throw new Error(`Could not find enabled button: ${label}`);
  }
  await cdp.send("Input.dispatchMouseEvent", {
    type: "mouseMoved",
    x: target.x,
    y: target.y,
    button: "none"
  });
  await cdp.send("Input.dispatchMouseEvent", {
    type: "mousePressed",
    x: target.x,
    y: target.y,
    button: "left",
    clickCount: 1
  });
  await cdp.send("Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x: target.x,
    y: target.y,
    button: "left",
    clickCount: 1
  });
  await sleep(600);
}

async function screenshot(cdp, fileName) {
  const result = await cdp.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: false
  });
  const filePath = path.join(screenshotsDir, fileName);
  await fs.writeFile(filePath, Buffer.from(result.data, "base64"));
  return filePath;
}

async function browserPageWebSocket(debugPort, targetUrl) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    try {
      const targets = await fetch(`http://127.0.0.1:${debugPort}/json/list`).then((response) => response.json());
      const page = targets.find((target) => target.type === "page" && String(target.url ?? "").startsWith(targetUrl));
      if (page?.webSocketDebuggerUrl) {
        return page.webSocketDebuggerUrl;
      }
    } catch {
      // Chrome may still be starting.
    }
    await sleep(250);
  }
  throw new Error("Chrome page debugger target did not appear.");
}

async function main() {
  await fs.mkdir(screenshotsDir, { recursive: true });
  await fs.access(bundledSampleWorkspace).catch(() => {
    throw new Error(`Bundled sample workspace is missing: ${bundledSampleWorkspace}`);
  });

  const python = pythonCommand();
  await fs.access(python).catch(() => {
    throw new Error(`Python venv is missing: ${python}. Run scripts/bootstrap-python.ps1 first.`);
  });

  const enginePort = await freePort();
  const vitePort = process.env.TEXTFLOW_SMOKE_VITE_PORT
    ? Number(process.env.TEXTFLOW_SMOKE_VITE_PORT)
    : await freePort();
  const chromePort = await freePort();
  const engineUrl = `http://127.0.0.1:${enginePort}`;
  const appUrl = `http://127.0.0.1:${vitePort}/`;
  const chrome = await firstExisting(chromeCandidates());
  const workspaceRoot = path.join(smokeRoot, "workspace");

  const engine = spawnLogged(python, ["main.py", "serve", "127.0.0.1", String(enginePort)], {
    cwd: engineRoot,
    env: {
      ...process.env,
      TEXTFLOW_WORKSPACE_ROOT: workspaceRoot,
      TEXTFLOW_BUNDLED_SAMPLE_WORKSPACE_ROOT: bundledSampleWorkspace,
      MPLCONFIGDIR: path.join(smokeRoot, "matplotlib"),
      PYTHONUTF8: "1"
    }
  });
  await waitForHttp(`${engineUrl}/health`, 20000, "Python engine");

  const npm = await npmInvocation();
  const vite = spawnLogged(npm.command, [
    ...npm.argsPrefix,
    "run",
    "dev",
    "--workspace",
    "apps/desktop",
    "--",
    "--host",
    "127.0.0.1",
    "--port",
    String(vitePort),
    "--strictPort"
  ], {
    cwd: repoRoot,
    env: {
      ...process.env,
      VITE_TEXTFLOW_ENGINE_URL: engineUrl
    }
  });
  await waitForHttp(appUrl, 30000, "Vite desktop frontend");

  const chromeProcess = spawnLogged(chrome, [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    `--remote-debugging-port=${chromePort}`,
    `--user-data-dir=${path.join(smokeRoot, "chrome-profile")}`,
    `--window-size=${viewport.width},${viewport.height}`,
    appUrl
  ], { cwd: repoRoot, env: process.env });

  const cdp = new CdpClient(await browserPageWebSocket(chromePort, appUrl));
  await cdp.connect();

  const browserErrors = [];
  cdp.on("Runtime.exceptionThrown", (params) => {
    browserErrors.push(params.exceptionDetails?.text ?? "Runtime exception");
  });
  cdp.on("Log.entryAdded", (params) => {
    if (params.entry?.level === "error") {
      const text = String(params.entry.text ?? "");
      if (text.includes("Failed to load resource") && text.includes("404")) {
        return;
      }
      browserErrors.push(text);
    }
  });

  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Log.enable");
  await waitForPredicate(cdp, `document.title === 'TextFlow Studio' && document.body.innerText.includes('项目对象')`, 30000, "workbench shell");
  await waitForPredicate(cdp, `document.body.innerText.includes('示例 01') && document.body.innerText.includes('节点图')`, 45000, "real sample project");

  const screenshots = [];
  const clickChecks = [];
  for (const step of [
    ["项目", "项目管理"],
    ["语料", "语料"],
    ["词库", "词库"],
    ["节点图", "节点图"],
    ["运行", "运行"],
    ["系统", "系统"]
  ]) {
    const [button, expectedText] = step;
    await clickButton(cdp, button);
    const ok = await evaluate(cdp, `document.body.innerText.includes(${JSON.stringify(expectedText)})`);
    clickChecks.push({ button, expectedText, ok });
    if (!ok) {
      throw new Error(`After clicking ${button}, expected text was not visible: ${expectedText}`);
    }
    screenshots.push(await screenshot(cdp, `${button}.png`));
  }

  await clickButton(cdp, "节点图");
  await waitForPredicate(cdp, `document.body.innerText.includes('运行节点图')`, 15000, "workflow command bar");
  await clickButton(cdp, "运行节点图");
  await waitForPredicate(
    cdp,
    `document.body.innerText.includes('运行流程完成') || document.body.innerText.includes('流程运行完成') || document.body.innerText.includes('completed')`,
    workflowTimeoutMs,
    "real workflow run"
  );
  screenshots.push(await screenshot(cdp, "workflow-run-complete.png"));

  const summary = await evaluate(cdp, `(() => ({
    title: document.title,
    textFlowEngineUrl: ${JSON.stringify(engineUrl)},
    hasRealProjectPath: document.body.innerText.includes('.tfproj') || document.body.innerText.includes('projects/'),
    bodyText: document.body.innerText.slice(0, 1200)
  }))()`);

  if (browserErrors.length) {
    throw new Error(`Browser errors were captured:\n${browserErrors.join("\n")}`);
  }

  cdp.close();
  console.log(JSON.stringify({
    ok: true,
    appUrl,
    engineUrl,
    workspaceRoot,
    viewport,
    workflowTimeoutMs,
    clickChecks,
    screenshots,
    summary
  }, null, 2));

  stopChild(chromeProcess.child);
  stopChild(vite.child);
  stopChild(engine.child);
}

main().catch(async (error) => {
  const details = {
    ok: false,
    error: error instanceof Error ? error.stack ?? error.message : String(error),
    smokeRoot,
    processLogs: processLogSummary()
  };
  console.error(JSON.stringify(details, null, 2));
  stopAllChildren();
  process.exit(1);
});

process.on("SIGINT", () => {
  stopAllChildren();
  process.exit(130);
});
