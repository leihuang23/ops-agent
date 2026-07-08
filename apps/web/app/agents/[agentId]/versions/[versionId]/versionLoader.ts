import type {
  AgentVersionDetailResult,
  AgentVersionPageResult,
} from '../../../../../lib/api';

type VersionLoaderOptions = {
  agentId: string;
  versionId: string;
  operatorToken: string | null;
  shouldRequestDetail: boolean;
  getSummary: (agentId: string, versionId: string) => Promise<AgentVersionPageResult>;
  getDetail: (
    agentId: string,
    versionId: string,
    options: { demoOperatorToken: string },
  ) => Promise<AgentVersionDetailResult>;
};

type VersionLoaderResult = {
  versionResult: AgentVersionPageResult | AgentVersionDetailResult;
  detailUnavailableMessage: string | null;
};

export function isOperatorAuthFailure(result: AgentVersionDetailResult) {
  return (
    !result.ok &&
    (result.error === 'Version endpoint returned HTTP 401' ||
      result.error === 'Version endpoint returned HTTP 403')
  );
}

export function shouldRequestProtectedDetail({
  operatorToken,
  detailUnlocked,
  draftSaved,
  publishError,
  versionError,
}: {
  operatorToken: string | null;
  detailUnlocked: boolean;
  draftSaved: boolean;
  publishError: string | null;
  versionError: string | null;
}) {
  return Boolean(
    operatorToken &&
      (detailUnlocked || draftSaved || publishError !== null || versionError !== null),
  );
}

export async function loadAgentVersionForPage({
  agentId,
  versionId,
  operatorToken,
  shouldRequestDetail,
  getSummary,
  getDetail,
}: VersionLoaderOptions): Promise<VersionLoaderResult> {
  if (!operatorToken || !shouldRequestDetail) {
    return {
      versionResult: await getSummary(agentId, versionId),
      detailUnavailableMessage: null,
    };
  }

  const detailResult = await getDetail(agentId, versionId, {
    demoOperatorToken: operatorToken,
  });
  if (detailResult.ok) {
    return {
      versionResult: detailResult,
      detailUnavailableMessage: null,
    };
  }

  return {
    versionResult: await getSummary(agentId, versionId),
    detailUnavailableMessage: isOperatorAuthFailure(detailResult)
      ? null
      : detailResult.error,
  };
}
