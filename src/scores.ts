/** The API derives skill_score from persisted, deterministically graded answers. */
export function skillScore(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? Math.min(10, Math.max(0, value)) : 0
}
export function formatSkillScore(value: unknown): string {
  return skillScore(value).toFixed(2)
}
