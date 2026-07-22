import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
  type QueryKey,
} from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";

import { useBulkGenerate, useGenerateDocument } from "./mutations";
import { documentKeys } from "./keys";
import { apiClient } from "@/shared/lib/api-client";

vi.mock("@/shared/lib/api-client", () => ({
  apiClient: {
    post: vi.fn(),
  },
}));

function renderWithClient<TResult>(hook: () => TResult) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
  const { result } = renderHook(hook, { wrapper });
  return { result, invalidateSpy };
}

function invalidatedKeys(spy: ReturnType<typeof vi.spyOn>): QueryKey[] {
  return spy.mock.calls.map(
    (call: unknown[]) => (call[0] as { queryKey: QueryKey }).queryKey,
  );
}

describe("documents mutations invalidation", () => {
  beforeEach(() => {
    vi.mocked(apiClient.post).mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("useGenerateDocument invalidates the documents list on success", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { documents: [], group_id: null },
    });
    const { result, invalidateSpy } = renderWithClient(() =>
      useGenerateDocument(),
    );

    result.current.mutate({
      template_version_id: "version-1",
      variables: { company_name: "Acme" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys(invalidateSpy)).toContainEqual(
      documentKeys.lists(),
    );
  });

  it("useBulkGenerate invalidates the documents list on success", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: {
        batch_id: "batch-1",
        document_count: 2,
        download_url: "/download",
        errors: [],
      },
    });
    const { result, invalidateSpy } = renderWithClient(() =>
      useBulkGenerate(),
    );

    result.current.mutate({
      templateVersionId: "version-1",
      file: new File(["x"], "rows.xlsx"),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys(invalidateSpy)).toContainEqual(
      documentKeys.lists(),
    );
  });
});
