import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const checkOnly = process.argv.includes("--check");

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(projectRoot, relativePath), "utf8"));
}

function writeJson(relativePath, value) {
  const target = path.join(projectRoot, relativePath);
  const next = `${JSON.stringify(value, null, 2)}\n`;
  writeIfChanged(relativePath, next, () => fs.writeFileSync(target, next, "utf8"));
}

function readText(relativePath) {
  return fs.readFileSync(path.join(projectRoot, relativePath), "utf8");
}

function writeText(relativePath, value) {
  const target = path.join(projectRoot, relativePath);
  writeIfChanged(relativePath, value, () => fs.writeFileSync(target, value, "utf8"));
}

function writeIfChanged(relativePath, next, writer) {
  const target = path.join(projectRoot, relativePath);
  const current = fs.existsSync(target) ? fs.readFileSync(target, "utf8") : "";
  if (current.replace(/\r\n/g, "\n") === next.replace(/\r\n/g, "\n")) {
    return;
  }
  if (checkOnly) {
    throw new Error(`${relativePath} is not synced with textflow.config.json`);
  }
  writer();
  console.log(`synced ${relativePath}`);
}

function replaceLineValue(source, pattern, replacement, relativePath) {
  if (!pattern.test(source)) {
    throw new Error(`${relativePath} did not match expected version pattern`);
  }
  return source.replace(pattern, replacement);
}

const config = readJson("textflow.config.json");
const version = String(config.product?.version ?? "").trim();
const productName = String(config.product?.name ?? "").trim();
const identifier = String(config.product?.identifier ?? "").trim();

if (!version || !productName || !identifier) {
  throw new Error("textflow.config.json requires product.name, product.identifier, and product.version");
}

const rootPackage = readJson("package.json");
rootPackage.version = version;
writeJson("package.json", rootPackage);

const desktopPackage = readJson("apps/desktop/package.json");
desktopPackage.version = version;
desktopPackage.dependencies["@textflow/shared-types"] = version;
writeJson("apps/desktop/package.json", desktopPackage);

const sharedTypesPackage = readJson("packages/shared-types/package.json");
sharedTypesPackage.version = version;
writeJson("packages/shared-types/package.json", sharedTypesPackage);

const tauriConfig = readJson("apps/desktop/src-tauri/tauri.conf.json");
tauriConfig.productName = productName;
tauriConfig.identifier = identifier;
tauriConfig.version = version;
if (Array.isArray(tauriConfig.app?.windows)) {
  tauriConfig.app.windows = tauriConfig.app.windows.map((windowConfig) => ({
    ...windowConfig,
    title: windowConfig.title === undefined ? windowConfig.title : productName
  }));
}
writeJson("apps/desktop/src-tauri/tauri.conf.json", tauriConfig);

const indexHtml = readText("apps/desktop/index.html");
writeText(
  "apps/desktop/index.html",
  replaceLineValue(indexHtml, /<title>.*<\/title>/, `<title>${productName}</title>`, "apps/desktop/index.html")
);

const cargoTomlPath = "apps/desktop/src-tauri/Cargo.toml";
let cargoToml = readText(cargoTomlPath);
cargoToml = replaceLineValue(cargoToml, /^version = ".*"$/m, `version = "${version}"`, cargoTomlPath);
writeText(cargoTomlPath, cargoToml);

const pyprojectPath = "services/python-engine/pyproject.toml";
let pyprojectToml = readText(pyprojectPath);
pyprojectToml = replaceLineValue(pyprojectToml, /^version = ".*"$/m, `version = "${version}"`, pyprojectPath);
writeText(pyprojectPath, pyprojectToml);

const packageLockPath = "package-lock.json";
const packageLock = readJson(packageLockPath);
packageLock.version = version;
if (packageLock.packages?.[""]) {
  packageLock.packages[""].version = version;
}
if (packageLock.packages?.["apps/desktop"]) {
  packageLock.packages["apps/desktop"].version = version;
  packageLock.packages["apps/desktop"].dependencies["@textflow/shared-types"] = version;
}
if (packageLock.packages?.["packages/shared-types"]) {
  packageLock.packages["packages/shared-types"].version = version;
}
writeJson(packageLockPath, packageLock);

if (checkOnly) {
  console.log("project config is synced");
}
