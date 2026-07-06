#!/usr/bin/env node
/**
 * Sync skills, recipes, workflows, and ops from the parent repo into site/src/data/catalog.json
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../..");
const SKILLS_ROOT = path.join(REPO_ROOT, "skills");
const WORKFLOWS_ROOT = path.join(REPO_ROOT, "docs/workflows");
const INDEX_PATH = path.join(SKILLS_ROOT, "index.json");
const OUT_PATH = path.join(__dirname, "../src/data/catalog.json");
const MEDIA_SRC = path.join(REPO_ROOT, "tests/fixtures");
const MEDIA_DST = path.join(__dirname, "../public/media");

const CATEGORY_META = {
  setup: { label: "Setup", icon: "wrench", order: 0 },
  inspect: { label: "Inspect", icon: "search", order: 1 },
  audio: { label: "Audio", icon: "waveform", order: 2 },
  transform: { label: "Image", icon: "image", order: 3 },
  video: { label: "Video", icon: "film", order: 4 },
  acquire: { label: "Acquire", icon: "download", order: 5 },
  timecode: { label: "Timecode", icon: "clock", order: 6 },
  captions: { label: "Captions", icon: "captions", order: 7 },
  vision: { label: "Vision", icon: "eye", order: 8 },
};

function readText(filePath) {
  return fs.readFileSync(filePath, "utf8");
}

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function parseSection(md, heading) {
  const re = new RegExp(`## ${heading}\\n([\\s\\S]*?)(?=\\n## |$)`);
  const match = md.match(re);
  return match ? match[1].trim() : "";
}

function parseBulletList(section) {
  if (!section) return [];
  return section
    .split("\n")
    .map((line) => line.replace(/^-\s+/, "").trim())
    .filter((line) => line && !line.startsWith("|"));
}

function parseRecipes(md) {
  const section = parseSection(md, "Recipes");
  if (!section) {
    const alt = md.match(/## Recipe:[^\n]*\n([\s\S]*?)(?=\n## |$)/g);
    if (!alt) return [];
    return alt.map((block) => {
      const titleMatch = block.match(/## (Recipe:[^\n]+)/);
      const title = titleMatch ? titleMatch[1].replace(/^Recipe:\s*/, "") : "Recipe";
      const body = block.replace(/^##[^\n]+\n/, "").trim();
      const bash = [...body.matchAll(/```bash\n([\s\S]*?)```/g)].map((m) => m[1].trim());
      const json = [...body.matchAll(/```json\n([\s\S]*?)```/g)].map((m) => m[1].trim());
      return {
        id: slugify(title),
        title,
        body,
        commands: bash,
        examples: json,
      };
    });
  }

  const recipes = [];
  const parts = section.split(/^### /m).filter(Boolean);
  for (const part of parts) {
    const lines = part.split("\n");
    const title = lines[0].trim();
    const body = lines.slice(1).join("\n").trim();
    const bash = [...body.matchAll(/```bash\n([\s\S]*?)```/g)].map((m) => m[1].trim());
    const json = [...body.matchAll(/```json\n([\s\S]*?)```/g)].map((m) => m[1].trim());
    recipes.push({
      id: slugify(title),
      title,
      body,
      commands: bash,
      examples: json,
    });
  }
  return recipes;
}

function parseScriptsTable(md) {
  const section = parseSection(md, "Available scripts");
  if (!section) return [];
  const rows = [];
  for (const line of section.split("\n")) {
    if (!line.startsWith("|") || line.includes("---") || line.includes("Script")) continue;
    const cells = line
      .split("|")
      .map((c) => c.trim())
      .filter(Boolean);
    if (cells.length >= 2) {
      rows.push({
        script: cells[0].replace(/`/g, ""),
        purpose: cells[1],
      });
    }
  }
  return rows;
}

function parseWorkflow(filePath) {
  const md = readText(filePath);
  const base = path.basename(filePath, ".md");
  if (base === "README") return null;

  const titleMatch = md.match(/^# Workflow:\s*(.+)/m);
  const title = titleMatch ? titleMatch[1].trim() : base;
  const summary = md.split("\n").find((l) => l && !l.startsWith("#"))?.trim() ?? "";

  const stepsSection = parseSection(md, "Steps") || parseSection(md, "One-shot pipeline");
  const optionalSection = parseSection(md, "Optional");
  const agentNotes = parseSection(md, "Agent notes");
  const related = parseSection(md, "Related skills");
  const skillsChain = related || "";
  const bash = [...md.matchAll(/```bash\n([\s\S]*?)```/g)].map((m) => m[1].trim());

  const relatedSkills = [...skillsChain.matchAll(/`([a-z][a-z0-9-]*)`/g)].map((m) => m[1]);

  return {
    id: slugify(title),
    slug: base,
    title,
    summary,
    steps: bash,
    optional: optionalSection,
    agentNotes,
    relatedSkills: [...new Set(relatedSkills)],
    skillsChain: related || undefined,
  };
}

function copyMedia() {
  fs.mkdirSync(MEDIA_DST, { recursive: true });
  for (const name of ["sample.mp4", "sample.png", "sample.wav", "sample.srt", "sample.vtt"]) {
    const src = path.join(MEDIA_SRC, name);
    if (fs.existsSync(src)) {
      fs.copyFileSync(src, path.join(MEDIA_DST, name));
    }
  }
}

function buildSearchIndex(skills, cookbooks, ops) {
  const items = [];

  for (const skill of skills) {
    items.push({
      type: "skill",
      id: skill.name,
      title: skill.name,
      subtitle: skill.categoryLabel,
      description: skill.description,
      url: `/skills/${skill.name}/`,
      keywords: [skill.name, skill.category, ...(skill.binaries ?? []), ...skill.ops.map((o) => o.op)].join(" "),
    });
    for (const recipe of skill.recipes) {
      items.push({
        type: "recipe",
        id: `${skill.name}:${recipe.id}`,
        title: recipe.title,
        subtitle: skill.name,
        description: recipe.body.slice(0, 200),
        url: `/skills/${skill.name}/#recipe-${recipe.id}`,
        keywords: `${skill.name} ${recipe.title} ${recipe.commands.join(" ")}`,
      });
    }
  }

  for (const book of cookbooks) {
    items.push({
      type: "cookbook",
      id: book.id,
      title: book.title,
      subtitle: "Cookbook",
      description: book.summary,
      url: `/cookbooks/${book.slug}/`,
      keywords: `${book.title} ${book.skillsChain} workflow cookbook`,
    });
  }

  for (const op of ops) {
    if (!op.op) continue;
    items.push({
      type: "op",
      id: op.op,
      title: op.op,
      subtitle: op.skill,
      description: op.script,
      url: `/ops/#${op.op.replace(/\./g, "-")}`,
      keywords: `${op.op} ${op.skill} ${op.script} ${(op.common_flags ?? []).join(" ")}`,
    });
  }

  return items;
}

function main() {
  const index = JSON.parse(readText(INDEX_PATH));
  const skills = [];

  for (const entry of index.skills) {
    const skillMdPath = path.join(SKILLS_ROOT, entry.name, "SKILL.md");
    const md = fs.existsSync(skillMdPath) ? readText(skillMdPath) : "";
    const category = entry.metadata?.["mediaskills-category"] ?? "other";
    const catMeta = CATEGORY_META[category] ?? { label: category, icon: "box", order: 99 };
    const binaries = entry.metadata?.["mediaskills-binaries"]?.split(",").map((s) => s.trim()) ?? [];

    skills.push({
      name: entry.name,
      description: entry.description,
      license: entry.license,
      compatibility: entry.compatibility,
      category,
      categoryLabel: catMeta.label,
      categoryIcon: catMeta.icon,
      categoryOrder: catMeta.order,
      binaries,
      doNotUseFor: parseBulletList(parseSection(md, "Do not use for")),
      recipes: parseRecipes(md),
      scriptsTable: parseScriptsTable(md),
      ops: entry.scripts.map((s) => ({
        script: s.script,
        op: s.op,
        language: s.language,
        common_flags: s.common_flags ?? [],
        pep723_dependencies: s.pep723_dependencies ?? [],
      })),
      opCount: entry.scripts.length,
      githubPath: `skills/${entry.name}`,
    });
  }

  skills.sort((a, b) => a.categoryOrder - b.categoryOrder || a.name.localeCompare(b.name));

  const cookbooks = fs
    .readdirSync(WORKFLOWS_ROOT)
    .filter((f) => f.endsWith(".md") && f !== "README.md")
    .map((f) => parseWorkflow(path.join(WORKFLOWS_ROOT, f)))
    .filter(Boolean);

  const ops = skills.flatMap((s) =>
    s.ops
      .filter((o) => o.op)
      .map((o) => ({
        ...o,
        skill: s.name,
        category: s.category,
        categoryLabel: s.categoryLabel,
      })),
  );

  const catalog = {
    generatedAt: new Date().toISOString(),
    version: index.version,
    repository: index.repository,
    spec: index.spec,
    skillCount: skills.length,
    opCount: ops.length,
    cookbookCount: cookbooks.length,
    categories: Object.entries(CATEGORY_META)
      .map(([id, meta]) => ({
        id,
        ...meta,
        skillCount: skills.filter((s) => s.category === id).length,
      }))
      .filter((c) => c.skillCount > 0)
      .sort((a, b) => a.order - b.order),
    skills,
    cookbooks,
    ops,
    searchIndex: buildSearchIndex(skills, cookbooks, ops),
    install: {
      pin: `@v${index.version}`,
      repo: "timelapsetech/mediaskills",
      commands: {
        list: `npx skills add timelapsetech/mediaskills@v${index.version} --list`,
        all: `npx skills add timelapsetech/mediaskills@v${index.version} --all`,
        one: `npx skills add timelapsetech/mediaskills@v${index.version} --skill inspect`,
        doctor: "bash skills/install-media-tools/scripts/doctor.sh",
      },
    },
  };

  fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true });
  fs.writeFileSync(OUT_PATH, JSON.stringify(catalog, null, 2));
  copyMedia();
  console.log(`Wrote ${OUT_PATH} (${skills.length} skills, ${cookbooks.length} cookbooks, ${ops.length} ops)`);
}

main();
