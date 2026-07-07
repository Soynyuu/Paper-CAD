import { spawn } from "node:child_process";
import { createInterface } from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";

const choices = [
    ["development", "通常のローカル開発"],
    ["demo", "オンラインデモ"],
    ["local_demo", "Wifiなしローカルデモ"],
];

function defaultEnv() {
    return process.env.NODE_ENV || "development";
}

async function selectEnv() {
    if (process.env.NODE_ENV) {
        return process.env.NODE_ENV;
    }

    const promptSetting = process.env.PAPER_CAD_ENV_PROMPT?.toLowerCase();
    if (promptSetting === "false" || promptSetting === "0" || promptSetting === "no") {
        return defaultEnv();
    }

    if (!process.stdin.isTTY || !process.stdout.isTTY) {
        return defaultEnv();
    }

    output.write("Frontend environmentを選択してください:\n");
    choices.forEach(([envName, description], index) => {
        output.write(`  ${index + 1}. ${envName} - ${description}\n`);
    });

    const rl = createInterface({ input, output });
    try {
        const answer = await rl.question("番号を入力 [1]: ");
        const selectedIndex = answer.trim() ? Number(answer.trim()) : 1;
        const choice = choices[selectedIndex - 1];
        return choice?.[0] || "development";
    } finally {
        rl.close();
    }
}

function run(command, args, envName) {
    return new Promise((resolve) => {
        output.write(`NODE_ENV=${envName} で起動します\n`);
        const child = spawn(command, args, {
            stdio: "inherit",
            shell: process.platform === "win32",
            env: {
                ...process.env,
                NODE_ENV: envName,
            },
        });

        child.on("exit", (code, signal) => {
            if (signal) {
                process.kill(process.pid, signal);
                return;
            }
            resolve(code ?? 0);
        });
    });
}

const commandName = process.argv[2] || "dev";
const envName = await selectEnv();

let exitCode = 1;
if (commandName === "dev") {
    if (envName === "development") {
        exitCode = await run("npx", ["rspack", "dev"], envName);
    } else {
        const scriptName = envName === "local_demo" ? "local_demo" : "demo";
        output.write(`${envName} は production build + static serve で起動します\n`);
        exitCode = await run("npm", ["run", scriptName], envName);
    }
} else {
    output.write(`Unknown command: ${commandName}\n`);
}

process.exit(exitCode);
