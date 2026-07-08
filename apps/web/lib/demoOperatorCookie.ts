export const VERSION_DETAIL_OPERATOR_COOKIE = 'ops_agent_version_operator_token';
export const VERSION_DETAIL_OPERATOR_COOKIE_MAX_AGE_SECONDS = 5 * 60;

export function agentVersionPath(agentId: string, versionId: string) {
  return `/agents/${encodeURIComponent(agentId)}/versions/${encodeURIComponent(versionId)}`;
}
