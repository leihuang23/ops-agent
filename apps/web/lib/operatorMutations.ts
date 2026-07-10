import 'server-only';

const ENABLED_VALUE = 'true';

export function operatorMutationsEnabled(): boolean {
  return process.env.OPERATOR_UI_ENABLED?.trim().toLowerCase() === ENABLED_VALUE;
}

export function requireOperatorMutationsEnabled(): void {
  if (!operatorMutationsEnabled()) {
    throw new Error(
      'Operator mutations are disabled for this deployment. Use a protected operator environment.',
    );
  }
}
