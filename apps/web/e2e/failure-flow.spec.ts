import { expect, test } from '@playwright/test';

test.describe('failure flow', () => {
  test('low-confidence report + rejected approval stays rejected', async ({ page }) => {
    test.setTimeout(180000);

    // 1. Navigate to the incidents list and open the ambiguous/unknown-root-cause
    //    incident (6th scenario). Its title is distinct from the deterministic
    //    scenarios, so we can target it directly.
    await page.goto('/incidents');
    await expect(page.getByRole('heading', { name: 'Incidents', exact: true })).toBeVisible();

    const ambiguousIncident = page.getByRole('link', {
      name: 'Paid MRR dropped with mixed renewal signals across accounts',
    });
    await ambiguousIncident.click();

    // 2. Start an inline investigation.
    await expect(page.locator('button:has-text("Run investigation")')).toBeVisible();
    await page.locator('button:has-text("Run investigation")').click();

    // 3. Wait for the report to render. The ambiguous scenario should produce
    //    a low or medium confidence report (not high).
    await expect(page.getByRole('heading', { name: 'Root cause', exact: true })).toBeVisible({
      timeout: 30000,
    });

    // The confidence pill must NOT be "high" — the ambiguous scenario should
    // yield low or medium confidence, proving the agent reports uncertainty
    // rather than hallucinating a specific root cause.
    const confidencePill = page.locator('[class*="confidence-pill"]');
    await expect(confidencePill).toBeVisible();
    const confidenceText = (await confidencePill.textContent()) ?? '';
    expect(confidenceText.toLowerCase()).not.toContain('high');

    // 4. Reject the pending request that belongs to this investigation run.
    // The full demo flow can create other pending approvals via eval runs, so
    // keep this assertion scoped to the current run instead of the global queue.
    const runApprovalPanel = page.locator('section.approval-panel');
    await expect(
      runApprovalPanel.getByRole('heading', { name: 'Approval queue' }),
    ).toBeVisible();

    const rejectButton = runApprovalPanel.getByRole('button', { name: 'Reject' }).first();
    await expect(rejectButton).toBeVisible();
    await rejectButton.click();

    // 5. The rejected approval must stay rejected for this run. Its status
    // badge should show "rejected" and the run-scoped Approve/Reject buttons
    // must be gone.
    await expect(runApprovalPanel.locator('.action-rejected').first()).toBeVisible();
    await expect(runApprovalPanel.getByRole('button', { name: 'Reject' })).toHaveCount(0);
    await expect(runApprovalPanel.getByRole('button', { name: 'Approve' })).toHaveCount(0);
  });
});
