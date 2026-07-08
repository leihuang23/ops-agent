'use server';

import { redirect } from 'next/navigation';
import { cookies } from 'next/headers';

import {
  approveApprovalRequest,
  createAgentVersion,
  createIncidentFromAnomaly,
  getAgentVersionDetail,
  publishAgentVersion as apiPublishAgentVersion,
  rejectApprovalRequest,
  runEvalSuite,
  startInvestigation,
  updateAgentVersion,
} from '@/lib/api';
import {
  VERSION_DETAIL_OPERATOR_COOKIE,
  VERSION_DETAIL_OPERATOR_COOKIE_MAX_AGE_SECONDS,
  agentVersionPath,
} from '@/lib/demoOperatorCookie';
import { resolveDemoOperatorToken } from '@/lib/demoOperatorToken';

export async function openIncidentFromAnomaly(formData: FormData) {
  const anomalyId = formData.get('anomaly_id');
  if (typeof anomalyId !== 'string' || anomalyId.length === 0) {
    throw new Error('Missing anomaly id');
  }

  const incident = await createIncidentFromAnomaly(anomalyId, await demoOperatorOptions(formData));
  if (!incident.ok) {
    redirect(`/?incident_error=${encodeURIComponent(incident.error)}`);
  }

  redirect(`/incidents/${encodeURIComponent(incident.data.id)}`);
}

export async function startInvestigationFromIncident(formData: FormData) {
  const incidentId = readRequiredFormValue(formData, 'incident_id');
  const agentVersionId = formData.get('agent_version_id');

  const encodedIncidentId = encodeURIComponent(incidentId);
  const options: { runInline: boolean; demoOperatorToken?: string; agentVersionId?: string } = {
    runInline: true,
    ...(await demoOperatorOptions(formData)),
  };
  if (typeof agentVersionId === 'string' && agentVersionId.length > 0) {
    options.agentVersionId = agentVersionId;
  }
  const run = await startInvestigation(incidentId, options);
  if (!run.ok) {
    redirect(`/incidents/${encodedIncidentId}?investigation_error=${encodeURIComponent(run.error)}`);
  }

  redirect(`/agent/runs/${encodeURIComponent(run.data.id)}`);
}

export async function approveApprovalFromRun(formData: FormData) {
  const approvalId = readRequiredFormValue(formData, 'approval_id');
  const runId = readRequiredFormValue(formData, 'run_id');
  const result = await approveApprovalRequest(
    approvalId,
    'Approved from the investigation approval queue.',
    await demoOperatorOptions(formData),
  );

  redirectToRun(runId, result.ok ? undefined : result.error);
}

export async function rejectApprovalFromRun(formData: FormData) {
  const approvalId = readRequiredFormValue(formData, 'approval_id');
  const runId = readRequiredFormValue(formData, 'run_id');
  const result = await rejectApprovalRequest(
    approvalId,
    'Rejected from the investigation approval queue.',
    await demoOperatorOptions(formData),
  );

  redirectToRun(runId, result.ok ? undefined : result.error);
}

export async function approveApprovalFromQueue(formData: FormData) {
  const approvalId = readRequiredFormValue(formData, 'approval_id');
  const result = await approveApprovalRequest(
    approvalId,
    'Approved from the global approvals queue.',
    await demoOperatorOptions(formData),
  );

  redirectToApprovals(result.ok ? undefined : result.error);
}

export async function rejectApprovalFromQueue(formData: FormData) {
  const approvalId = readRequiredFormValue(formData, 'approval_id');
  const result = await rejectApprovalRequest(
    approvalId,
    'Rejected from the global approvals queue.',
    await demoOperatorOptions(formData),
  );

  redirectToApprovals(result.ok ? undefined : result.error);
}

export async function runEvalSuiteFromReport(formData: FormData) {
  const evalRunToken = formData.get('eval_run_token');
  const result = await runEvalSuite(
    typeof evalRunToken === 'string' && evalRunToken.length > 0
      ? evalRunToken
      : undefined,
  );
  if (!result.ok) {
    redirect(`/evals?eval_error=${encodeURIComponent(result.error)}`);
  }

  if (result.data.status === 'running') {
    redirect(
      `/evals?eval_notice=${encodeURIComponent(
        'Eval suite enqueued — results will be available shortly.',
      )}`,
    );
  }

  redirect('/evals');
}

export async function saveAgentVersionDraft(formData: FormData) {
  const agentId = readRequiredFormValue(formData, 'agent_id');
  const versionId = formData.get('version_id');
  const baseVersionId = formData.get('base_version_id');
  const systemPrompt = formData.get('system_prompt');
  const model = formData.get('model');
  const temperatureRaw = formData.get('temperature');
  const maxTokensRaw = formData.get('max_tokens');
  const toolsPresent = formData.get('enabled_tool_ids_present');
  const systemPromptPresent = formData.has('system_prompt');
  const returnTo = formData.get('return_to');

  const returnPath =
    typeof returnTo === 'string' && returnTo.length > 0 ? returnTo : `/agents/${encodeURIComponent(agentId)}`;

  const enabledToolIds: string[] =
    toolsPresent === '1'
      ? formData.getAll('enabled_tool_ids').filter((v): v is string => typeof v === 'string')
      : [];
  const shouldSetEnabledTools = toolsPresent === '1';

  let temperature: number | undefined;
  if (typeof temperatureRaw === 'string' && temperatureRaw.length > 0) {
    temperature = Number(temperatureRaw);
    if (Number.isNaN(temperature)) {
      redirect(`${returnPath}?version_error=${encodeURIComponent('Invalid temperature value')}`);
    }
  }

  let maxTokens: number | undefined;
  if (typeof maxTokensRaw === 'string' && maxTokensRaw.length > 0) {
    maxTokens = Number(maxTokensRaw);
    if (Number.isNaN(maxTokens) || maxTokens <= 0) {
      redirect(`${returnPath}?version_error=${encodeURIComponent('Invalid max tokens value')}`);
    }
  }

  const versionInput = {
    system_prompt:
      systemPromptPresent && typeof systemPrompt === 'string'
        ? systemPrompt
        : undefined,
    model: typeof model === 'string' && model.length > 0 ? model : undefined,
    temperature,
    max_tokens: maxTokens,
    enabled_tool_ids: shouldSetEnabledTools ? enabledToolIds : undefined,
  };

  let result;
  if (typeof versionId === 'string' && versionId.length > 0) {
    result = await updateAgentVersion(
      agentId,
      versionId,
      versionInput,
      await demoOperatorOptions(formData, agentId, versionId),
    );
  } else {
    const sourceVersionId =
      typeof baseVersionId === 'string' && baseVersionId.length > 0 ? baseVersionId : undefined;
    result = await createAgentVersion(
      agentId,
      {
        fork_from_version_id: sourceVersionId,
        ...versionInput,
      },
      await demoOperatorOptions(formData, agentId, sourceVersionId),
    );
  }

  if (!result.ok) {
    redirect(`${returnPath}?version_error=${encodeURIComponent(result.error)}`);
  }

  if (result.data.version_number === null) {
    redirect(`/agents/${encodeURIComponent(agentId)}/versions/${encodeURIComponent(result.data.id)}?draft_saved=1`);
  }

  redirect(returnPath);
}

export async function publishAgentVersion(formData: FormData) {
  const versionId = readRequiredFormValue(formData, 'version_id');
  const agentId = readRequiredFormValue(formData, 'agent_id');

  const result = await apiPublishAgentVersion(
    agentId,
    versionId,
    await demoOperatorOptions(formData, agentId, versionId),
  );

  if (!result.ok) {
    redirect(
      `/agents/${encodeURIComponent(agentId)}/versions/${encodeURIComponent(versionId)}?publish_error=${encodeURIComponent(result.error)}`,
    );
  }

  redirect(`/agents/${encodeURIComponent(agentId)}?version_published=${encodeURIComponent(versionId)}`);
}

export async function unlockAgentVersionDetail(formData: FormData) {
  const agentId = readRequiredFormValue(formData, 'agent_id');
  const versionId = readRequiredFormValue(formData, 'version_id');
  const operatorToken = readRequiredFormValue(formData, 'operator_token');
  const returnPath = agentVersionPath(agentId, versionId);

  const detail = await getAgentVersionDetail(agentId, versionId, {
    demoOperatorToken: operatorToken,
  });
  if (!detail.ok) {
    redirect(`${returnPath}?version_error=${encodeURIComponent(detail.error)}`);
  }

  const cookieStore = await cookies();
  cookieStore.set(VERSION_DETAIL_OPERATOR_COOKIE, operatorToken, {
    httpOnly: true,
    sameSite: 'strict',
    secure: process.env.NODE_ENV === 'production',
    maxAge: VERSION_DETAIL_OPERATOR_COOKIE_MAX_AGE_SECONDS,
    path: returnPath,
  });

  redirect(`${returnPath}?detail_unlocked=1`);
}

function readRequiredFormValue(formData: FormData, key: string) {
  const value = formData.get(key);
  if (typeof value !== 'string' || value.length === 0) {
    throw new Error(`Missing ${key}`);
  }
  return value;
}

async function demoOperatorOptions(
  formData: FormData,
  agentId?: string,
  versionId?: string,
) {
  const operatorToken = formData.get('operator_token');
  let cookieToken: string | undefined;
  if (agentId && versionId) {
    const cookieStore = await cookies();
    const cookie = cookieStore.get(VERSION_DETAIL_OPERATOR_COOKIE);
    cookieToken = cookie?.value;
  }
  return {
    demoOperatorToken: resolveDemoOperatorToken(operatorToken, cookieToken),
  };
}

function redirectToRun(runId: string, error?: string) {
  const encodedRunId = encodeURIComponent(runId);
  if (error) {
    redirect(`/agent/runs/${encodedRunId}?approval_error=${encodeURIComponent(error)}`);
  }
  redirect(`/agent/runs/${encodedRunId}`);
}

function redirectToApprovals(error?: string) {
  if (error) {
    redirect(`/approvals?approval_error=${encodeURIComponent(error)}`);
  }
  redirect('/approvals');
}
