// Playwright MCP 실행기 (Claude Code가 .mcp.json에서 부른다)
//
// - 클라우드 세션처럼 /opt/pw-browsers/chromium 이 있으면 그 Chromium을 쓴다 (따로 내려받지 않음).
// - 내 컴퓨터에서는 Playwright가 설치한 브라우저를 쓴다. 처음 한 번: npx playwright install chromium
// - 창을 띄워서 보고 싶으면 환경변수 PLAYWRIGHT_MCP_HEADED=1
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";

const VERSION = "0.0.86"; // 고정해서 팀원 모두 같은 버전을 쓰게 함
const args = ["-y", `@playwright/mcp@${VERSION}`, "--isolated"];
if (process.env.PLAYWRIGHT_MCP_HEADED !== "1") args.push("--headless");

const chromium = process.env.PLAYWRIGHT_CHROMIUM_PATH || "/opt/pw-browsers/chromium";
if (existsSync(chromium)) args.push("--browser", "chromium", "--executable-path", chromium, "--no-sandbox");

const isWin = process.platform === "win32";
const child = spawn(isWin ? "npx.cmd" : "npx", args, { stdio: "inherit", shell: isWin });
child.on("exit", (code) => process.exit(code ?? 0));
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => child.kill(sig));
