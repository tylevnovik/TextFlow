import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

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
    await new Promise((resolve) => setTimeout(resolve, 350));
  }
  const visibleText = await evaluate(cdp, `document.body?.innerText?.slice(0, 1400) ?? ""`, 1000).catch(() => "");
  throw new Error(`Timed out waiting for ${label}.\nVisible text:\n${visibleText}`);
}

async function clickButton(cdp, label) {
  const target = await evaluate(cdp, `
    (() => {
      const wanted = ${JSON.stringify(label)};
      const elements = Array.from(document.querySelectorAll('button,[role="button"],a,[role="tab"],[role="treeitem"]'));
      for (const element of elements) {
        const text = (element.innerText || element.textContent || '').trim();
        const aria = (element.getAttribute('aria-label') || '').trim();
        const title = (element.getAttribute('title') || '').trim();
        const strongEl = element.querySelector('strong');
        const strongText = strongEl ? (strongEl.innerText || strongEl.textContent || '').trim() : '';
        
        const disabled = element.disabled || element.getAttribute('aria-disabled') === 'true';
        const rect = element.getBoundingClientRect();
        
        const matches = text === wanted || 
                        aria === wanted || 
                        title === wanted || 
                        strongText === wanted;
                        
        if (!disabled && rect.width > 0 && rect.height > 0 && matches) {
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
    throw new Error(`Could not find enabled click target: ${label}`);
  }
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: target.x, y: target.y, button: "none" });
  await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: target.x, y: target.y, button: "left", clickCount: 1 });
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: target.x, y: target.y, button: "left", clickCount: 1 });
  await new Promise((resolve) => setTimeout(resolve, 600));
}

async function clickSelector(cdp, selector) {
  const target = await evaluate(cdp, `
    (() => {
      const element = document.querySelector(${JSON.stringify(selector)});
      if (!element) return null;
      const rect = element.getBoundingClientRect();
      return {
        x: Math.round(rect.left + rect.width / 2),
        y: Math.round(rect.top + rect.height / 2)
      };
    })()
  `);
  if (!target) {
    throw new Error(`Could not find selector: ${selector}`);
  }
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: target.x, y: target.y, button: "none" });
  await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: target.x, y: target.y, button: "left", clickCount: 1 });
  await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: target.x, y: target.y, button: "left", clickCount: 1 });
  await new Promise((resolve) => setTimeout(resolve, 600));
}

async function screenshot(cdp, screenshotsDir, fileName) {
  const result = await cdp.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: false
  });
  const filePath = path.join(screenshotsDir, fileName);
  await fs.writeFile(filePath, Buffer.from(result.data, "base64"));
  return filePath;
}

async function setViewport(cdp, width, height) {
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: false
  });
  await new Promise((resolve) => setTimeout(resolve, 400));
}

async function findLatestSession() {
  const tempDir = os.tmpdir();
  const dirs = await fs.readdir(tempDir);
  const sessionDirs = [];
  for (const name of dirs) {
    if (name.startsWith("textflow-real-stack-")) {
      const dirPath = path.join(tempDir, name);
      try {
        const stat = await fs.stat(dirPath);
        if (stat.isDirectory()) {
          const sessionPath = path.join(dirPath, "session.json");
          await fs.access(sessionPath);
          const parts = name.split("-");
          const time = parseInt(parts[parts.length - 1] || "0", 10);
          if (!isNaN(time)) {
            sessionDirs.push({ name, time, sessionPath });
          }
        }
      } catch (err) {
        // Skip invalid directory or missing file
      }
    }
  }

  sessionDirs.sort((a, b) => b.time - a.time);

  if (sessionDirs.length === 0) {
    throw new Error("No valid textflow-real-stack temp directory with session.json found.");
  }

  const data = await fs.readFile(sessionDirs[0].sessionPath, "utf8");
  return JSON.parse(data);
}

async function browserPageWebSocket(debugUrl) {
  const targets = await fetch(debugUrl).then((res) => res.json());
  // Find target type "page"
  const page = targets.find((target) => target.type === "page");
  if (!page?.webSocketDebuggerUrl) {
    throw new Error(`Chrome page debugger target not found in targets list: ${JSON.stringify(targets)}`);
  }
  return page.webSocketDebuggerUrl;
}

async function runExploration() {
  console.log("Locating latest real dev stack session...");
  const session = await findLatestSession();
  console.log(`Found session initialized at ${session.workspaceRoot}`);
  
  const debugUrl = session.chromeDebugUrl;
  const wsUrl = await browserPageWebSocket(debugUrl);
  console.log(`Connecting to CDP via ${wsUrl}...`);
  
  const cdp = new CdpClient(wsUrl);
  await cdp.connect();
  console.log("Connected to Chrome debugging port!");

  // Track browser errors
  const browserErrors = [];
  cdp.on("Runtime.exceptionThrown", (params) => {
    browserErrors.push({
      type: "exception",
      text: params.exceptionDetails?.text ?? "Runtime exception",
      details: params.exceptionDetails?.exception?.description || ""
    });
  });
  cdp.on("Log.entryAdded", (params) => {
    if (params.entry?.level === "error") {
      const text = String(params.entry.text ?? "");
      if (!text.includes("Failed to load resource") || !text.includes("404")) {
        browserErrors.push({
          type: "console-error",
          text,
          url: params.entry.url
        });
      }
    }
  });

  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Log.enable");
  await cdp.send("Network.enable");

  const networkRequests = [];
  cdp.on("Network.requestWillBeSent", (params) => {
    if (params.request?.url?.includes("/tasks/")) {
      networkRequests.push({
        type: "request",
        time: new Date().toLocaleTimeString(),
        method: params.request.method,
        url: params.request.url
      });
    }
  });
  cdp.on("Network.responseReceived", (params) => {
    if (params.response?.url?.includes("/tasks/")) {
      networkRequests.push({
        type: "response",
        time: new Date().toLocaleTimeString(),
        status: params.response.status,
        url: params.response.url
      });
    }
  });

  const sdir = session.screenshotsDir;
  console.log(`Screenshots will be stored in ${sdir}`);

  // Ensure standard viewport first
  console.log("Setting standard viewport 1280x720...");
  await setViewport(cdp, 1280, 720);

  // Wait for bootstrap project to load completely
  console.log("Waiting for bootstrap project '示例 01' to load...");
  await waitForPredicate(cdp, `document.body.innerText.includes('示例 01') && document.body.innerText.includes('三核心概览')`, 25000, "project load");
  console.log("Project loaded!");

  // 1. Traverse all pages at standard resolution
  console.log("\n--- Phase 1: Traversing main pages at 1280x720 ---");
  const pages = [
    { label: "项目", expect: "项目概览" },
    { label: "语料", expect: "语料工作面" },
    { label: "词库", expect: "词库工作面" },
    { label: "节点图", expect: "运行节点图" },
    { label: "运行", expect: "运行支撑面" },
    { label: "系统", expect: "应用设置" }
  ];

  for (const page of pages) {
    console.log(`Navigating to page: ${page.label}`);
    await clickButton(cdp, page.label);
    await waitForPredicate(cdp, `document.body.innerText.includes(${JSON.stringify(page.expect)})`, 5000, `Page ${page.label}`);
    const snap = await screenshot(cdp, sdir, `1280_page_${page.label}.png`);
    console.log(`Captured screenshot: ${snap}`);
  }

  // 2. Perform deep interaction in Lexicon page
  console.log("\n--- Phase 2: Interacting with Lexicon lists ---");
  await clickButton(cdp, "词库");
  
  // Click stopwords lexicon node in the tree or sidebar if available
  // We can try to select specific lexicon sub-items. For example:
  // In the left sidebar: 停用词, 自定义词典, 同义词表, 近义词表
  // Let's click "停用词" and "自定义词典"
  const lexiconSubItems = ["停用词", "自定义词典", "同义词表", "排除词表"];
  for (const sub of lexiconSubItems) {
    console.log(`Clicking lexicon category: ${sub}`);
    try {
      await clickButton(cdp, sub);
      const lexiconSnap = await screenshot(cdp, sdir, `1280_lexicon_${sub}.png`);
      console.log(`Lexicon ${sub} displayed. Captured: ${lexiconSnap}`);
    } catch (err) {
      console.warn(`Could not select lexicon item "${sub}": ${err.message}`);
    }
  }

  // 3. Perform deep interaction in Corpus page
  console.log("\n--- Phase 3: Interacting with Corpus documents ---");
  await clickButton(cdp, "语料");
  // Check if we can click on a document row in the Corpus table to open the property inspector
  // Fluent UI DataGrid rows often have role="row"
  console.log("Checking for corpus data rows...");
  const clickedRow = await evaluate(cdp, `
    (() => {
      // Find cells or rows in the DataGrid containing some corpus data
      // Let's click the first cell in DataGridBody that is not empty
      const cells = Array.from(document.querySelectorAll('[role="gridcell"], .fui-DataGridCell'));
      for (const cell of cells) {
        if (cell.innerText && cell.innerText.trim().length > 3) {
          const rect = cell.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            return { x: Math.round(rect.left + rect.width / 2), y: Math.round(rect.top + rect.height / 2) };
          }
        }
      }
      return null;
    })()
  `);
  if (clickedRow) {
    console.log("Clicking a corpus document cell...");
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: clickedRow.x, y: clickedRow.y, button: "none" });
    await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: clickedRow.x, y: clickedRow.y, button: "left", clickCount: 1 });
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: clickedRow.x, y: clickedRow.y, button: "left", clickCount: 1 });
    await new Promise((resolve) => setTimeout(resolve, 800));
    const corpusSelectSnap = await screenshot(cdp, sdir, `1280_corpus_doc_selected.png`);
    console.log(`Document selected. Captured: ${corpusSelectSnap}`);
  } else {
    console.log("No corpus grid cell found to click.");
  }

  // 4. Run the Workflow Graph and trace progress
  console.log("\n--- Phase 4: Running Workflow Graph ---");
  await clickButton(cdp, "节点图");
  await waitForPredicate(cdp, `document.body.innerText.includes('运行节点图')`, 5000, "Workflow command bar ready");
  
  const buttonStatus = await evaluate(cdp, `
    (() => {
      const btn = Array.from(document.querySelectorAll('button,[role="button"]'))
        .find(el => (el.innerText || el.textContent || '').trim().includes('运行节点图'));
      return btn ? {
        exists: true,
        disabled: btn.disabled || btn.getAttribute('aria-disabled') === 'true',
        classes: btn.className,
        text: btn.innerText
      } : { exists: false };
    })()
  `);
  console.log("Button Status before click:", JSON.stringify(buttonStatus, null, 2));

  console.log("Triggering '运行节点图'...");
  await clickButton(cdp, "运行节点图");
  console.log("Waiting for workflow completion (up to 3 minutes)...");
  
  try {
    const startTime = Date.now();
    let finished = false;
    let statusLogCount = 0;
    while (Date.now() - startTime < 180000) {
      const isCompleted = await evaluate(cdp, `
        document.body.innerText.includes('运行流程完成') || 
        document.body.innerText.includes('流程运行完成') || 
        document.body.innerText.includes('completed')
      `);
      if (isCompleted) {
        finished = true;
        break;
      }
      
      if (statusLogCount % 10 === 0) {
        const paneText = await evaluate(cdp, `
          (() => {
            const pane = document.querySelector('.workbench-bottom-pane-host, .status-panel, [role="status"]');
            return pane ? pane.innerText.trim().replace(/\\n/g, ' | ') : 'No status pane visible';
          })()
        `);
        console.log(`[Workflow Run Progress] Elapsed: ${Math.round((Date.now() - startTime) / 1000)}s | Status: ${paneText}`);
      }
      statusLogCount++;
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    
    if (finished) {
      console.log("Workflow execution finished successfully!");
    } else {
      throw new Error("Timed out waiting for Workflow run finish.");
    }
  } catch (err) {
    console.error(`Workflow execution timed out or failed! Error: ${err.message}`);
    const failSnap = await screenshot(cdp, sdir, `workflow_failed.png`);
    console.log(`Saved failure state screenshot to: ${failSnap}`);
  }

  const finishedSnap = await screenshot(cdp, sdir, `1280_workflow_run_finished.png`);
  console.log(`Captured finished workflow screenshot: ${finishedSnap}`);

  // Navigate to runs and artifacts to verify they were updated
  console.log("Navigating to Runs page to verify generated artifacts...");
  await clickButton(cdp, "运行");
  await new Promise((resolve) => setTimeout(resolve, 1000));
  const runsSnap = await screenshot(cdp, sdir, `1280_runs_after_execution.png`);
  console.log(`Runs list screenshot: ${runsSnap}`);

  // 5. Test Responsive layouts
  console.log("\n--- Phase 5: Testing Responsive Layouts ---");
  const responsiveResolutions = [
    { name: "small_800x600", w: 800, h: 600 },
    { name: "medium_1024x768", w: 1024, h: 768 },
    { name: "large_1920x1080", w: 1920, h: 1080 }
  ];

  for (const res of responsiveResolutions) {
    console.log(`Setting viewport: ${res.name} (${res.w}x${res.h})`);
    await setViewport(cdp, res.w, res.h);
    
    // Take a screenshot of the main workspaces to check for squeezing/clipping
    for (const pageName of ["语料", "节点图"]) {
      await clickButton(cdp, pageName);
      await new Promise((resolve) => setTimeout(resolve, 500));
      const resSnap = await screenshot(cdp, sdir, `${res.name}_page_${pageName}.png`);
      console.log(`Captured screenshot: ${resSnap}`);
    }
  }

  // Restore standard viewport
  await setViewport(cdp, 1280, 720);

  cdp.close();
  console.log("\n--- Exploration Complete! ---");
  console.log(`Captured screenshots are in directory: ${sdir}`);
  
  if (browserErrors.length > 0) {
    console.log("\nCaptured browser console/runtime errors:");
    console.log(JSON.stringify(browserErrors, null, 2));
  } else {
    console.log("\nNo console errors or exceptions were captured.");
  }

  console.log("\nCaptured Network task requests (last 30):");
  console.log(JSON.stringify(networkRequests.slice(-30), null, 2));

  // Return execution summary
  return {
    ok: true,
    browserErrors,
    screenshotsDir: sdir
  };
}

runExploration().catch((err) => {
  console.error("Exploration script failed:", err);
  process.exit(1);
});
