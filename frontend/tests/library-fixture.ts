import { expect, test as base, type APIRequestContext } from "@playwright/test";

type Publication = { id: string; version: number; published_id: string | null; owner: { id: { value: string } } };
const apiUrl = `http://127.0.0.1:${process.env.SMOKE_API_PORT ?? "8000"}`;

async function documents(request: APIRequestContext): Promise<Publication[]> {
  const result: Publication[] = [];
  for (let offset = 0; ; offset += 100) {
    const response = await request.get(`${apiUrl}/library/documents?offset=${offset}&limit=100`);
    expect(response.ok()).toBe(true);
    const page = await response.json() as Publication[];
    result.push(...page);
    if (page.length < 100) return result;
  }
}

/** Identical fixture passages must not compete in later tests' deduplicated search. */
export const test = base.extend<{ isolatePublications: void }>({
  isolatePublications: [async ({ request }, use) => {
    const existing = new Set((await documents(request)).map(document => document.id));
    await use();
    for (const document of await documents(request)) {
      if (existing.has(document.id) || !document.published_id) continue;
      const response = await request.post(`${apiUrl}/library/documents/${document.id}/withdrawal`, {
        headers: { "X-Fake-Actor-Id": document.owner.id.value },
        data: { expected_version: document.version, reason: "Synthetic browser fixture completed" },
      });
      expect(response.ok(), await response.text()).toBe(true);
    }
  }, { auto: true }],
});
