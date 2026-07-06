import catalog from "../data/catalog.json";

export type Catalog = typeof catalog;
export type Skill = Catalog["skills"][number];
export type Cookbook = Catalog["cookbooks"][number];
export type Op = Catalog["ops"][number];
export type SearchItem = Catalog["searchIndex"][number];
export type Category = Catalog["categories"][number];

export function getCatalog(): Catalog {
  return catalog;
}

export function getSkill(slug: string): Skill | undefined {
  return catalog.skills.find((s) => s.name === slug);
}

export function getCookbook(slug: string): Cookbook | undefined {
  return catalog.cookbooks.find((c) => c.slug === slug || c.id === slug);
}

export function getSkillsByCategory(categoryId: string): Skill[] {
  return catalog.skills.filter((s) => s.category === categoryId);
}

export function getRelatedCookbooks(skillName: string): Cookbook[] {
  return catalog.cookbooks.filter((c) => c.relatedSkills?.includes(skillName));
}
