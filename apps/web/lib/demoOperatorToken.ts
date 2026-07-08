export function resolveDemoOperatorToken(
  formToken: FormDataEntryValue | null,
  cookieToken: string | undefined,
) {
  if (typeof formToken === 'string' && formToken.length > 0) {
    return formToken;
  }
  return cookieToken;
}
