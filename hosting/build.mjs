// Hosting adapter. Python remains the reference implementation.
import { readFileSync, mkdirSync, writeFileSync, copyFileSync } from "node:fs";
import { execFileSync } from "node:child_process";

const snapshot = JSON.parse(execFileSync("python", ["-c",
  "import json; from data import generate,CITIES,SKILLS,LANGUAGES,SHIFTS; from learning import train; from matching import WEIGHTS; n,r=generate(); print(json.dumps(dict(nurses=n,requests=r,cities=CITIES,skills=SKILLS,languages=LANGUAGES,shifts=SHIFTS,weights=dict(default=WEIGHTS,learned=train(n)))))"
], { encoding: "utf8" }));
const assets = Object.fromEntries(
  [["/", "index.html", "text/html"], ["/style.css", "style.css", "text/css"], ["/app.js", "app.js", "text/javascript"]]
    .map(([path, file, type]) => [path, { body: readFileSync("web/" + file, "utf8"), type }])
);
const adapter = readFileSync("hosting/worker.mjs", "utf8");
mkdirSync("dist/server", { recursive: true });
mkdirSync("dist/.openai", { recursive: true });
writeFileSync("dist/server/index.js",
  "const dataset = " + JSON.stringify(snapshot) + ";\nconst assets = " + JSON.stringify(assets) + ";\n" + adapter);
copyFileSync(".openai/hosting.json", "dist/.openai/hosting.json");
console.log("Built Worker with Python-generated profiles and fitted weights.");
